# archives/views.py
from datetime import timedelta
import csv

from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.db import transaction

from .models import ArchiveWeekly
from plans.models import WeeklyPlan  # للـ sync


# ---- صلاحيات ----
def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


# ---- صفحة الأرشيف (فلاتر + جدول + Export CSV + KPIs) ----
@login_required
@user_passes_test(is_manager)
def archives_list(request):
    """
    صفحة الأرشيف + فلاتر + Export CSV
    (تم فصل السِنك في فيو مستقل: POST /archives/sync/)
    """
    qs = ArchiveWeekly.objects.all()

    # Quick range by archived_at (افتراضي 365 يوم)
    quick = request.GET.get('quick', '365')
    if quick.isdigit():
        days = int(quick)
        qs = qs.filter(archived_at__gte=timezone.now() - timedelta(days=days))

    # فلاتر تاريخ الـ planned_date
    d_from = request.GET.get('from')
    d_to = request.GET.get('to')
    if d_from:
        qs = qs.filter(planned_date__gte=d_from)
    if d_to:
        qs = qs.filter(planned_date__lte=d_to)

    # بحث نصي
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(rep__username__icontains=q) |
            Q(entity_type__icontains=q) |
            Q(specialization__icontains=q) |
            Q(visit_objective__icontains=q) |
            Q(entity_address__icontains=q) |  # بدل address/account
            Q(notes__icontains=q) |
            Q(status__icontains=q) |
            Q(aa_plan__icontains=q) |
            Q(targeted_line__icontains=q)
        )

    # ----- Export CSV (يحترم نفس الفلاتر) -----
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="archives.csv"'

        # BOM عشان Excel يقرأ UTF-8 عربي صح
        resp.write('\ufeff')

        # lineterminator لتفادي سطر فاضي في ويندوز/Excel
        w = csv.writer(resp, lineterminator='\n')

        w.writerow([
            '#', 'Archived At', 'Planned Date', 'Week #', 'Rep', 'Aa Plan',
            'Targeted Line', 'Entity Type', 'Specialization', 'Visit Objective',
            'Address', 'Notes', 'Status'
        ])
        for r in qs.order_by('-archived_at', '-id'):
            w.writerow([
                r.id,
                r.archived_at.strftime('%Y-%m-%d %H:%M:%S') if r.archived_at else '',
                r.planned_date or '',
                r.week_no or '',
                (r.rep.get_username() if r.rep_id else ''),
                r.aa_plan or '',
                r.targeted_line or '',
                r.entity_type or '',
                r.specialization or '',
                r.visit_objective or '',
                r.entity_address or '',  # الاسم النهائي بدل r.address
                r.notes or '',
                r.status or '',
            ])
        return resp

    # KPIs
    k_rows = qs.count()
    k_reps = qs.values('rep_id').distinct().count()
    k_accounts = qs.exclude(entity_address='').values('entity_address').distinct().count()  # بدل account
    k_last = qs.order_by('-archived_at').values_list('archived_at', flat=True).first()

    # Rows للجدول
    rows = qs.order_by('-archived_at', '-id')[:500]

    ctx = {
        'rows': rows,
        'k_rows': k_rows,
        'k_reps': k_reps,
        'k_accounts': k_accounts,
        'k_last': k_last,
    }
    return render(request, 'archives/archives.html', ctx)


# ---- مزامنة من الويكلي للأرشيف (POST فقط) ----
@login_required
@user_passes_test(is_manager)
@require_POST
def sync_archives(request):
    """
    يعمل Snapshot/توحيد للأرشيف لكل (rep, week_no) موجودين في WeeklyPlan بحالة approved.
    يتعامل مع الدوبلكيت: يدمج العدادات ويحذف الزيادات.
    يرجّع JSON بدل HTML علشان الفرونت مايكسرش.
    """
    created = 0
    merged  = 0
    touched = 0

    # كل الأزواج (rep_id, week_number) الموثّقة approved
    pairs = (WeeklyPlan.objects
             .filter(status='approved')
             .values('rep_id', 'week_number')
             .distinct())

    for row in pairs:
        rep_id  = row['rep_id']
        week_no = row['week_number']

        # أي Plan مرجعية لنفس الأسبوع لتعبئة التفاصيل
        p = (WeeklyPlan.objects
             .filter(rep_id=rep_id, week_number=week_no, status='approved')
             .order_by('planned_date', 'id')
             .first())

        defaults = {
            'planned_date'   : getattr(p, 'planned_date', None),
            'aa_plan'        : getattr(p, 'aa_plan', ''),
            'targeted_line'  : getattr(p, 'product_line', ''),
            'entity_type'    : getattr(p, 'entity_type', ''),
            'specialization' : getattr(p, 'specialization', ''),
            'visit_objective': getattr(p, 'visit_objective', ''),
            'entity_address' : getattr(p, 'entity_address', ''),
            'notes'          : getattr(p, 'notes', ''),
            'status'         : 'Approved',
        }

        with transaction.atomic():
            qs = ArchiveWeekly.objects.select_for_update().filter(rep_id=rep_id, week_no=week_no).order_by('id')
            if not qs.exists():
                ArchiveWeekly.objects.create(rep_id=rep_id, week_no=week_no, **defaults)
                created += 1
            else:
                aw = qs.first()
                # حدّث الحقول من آخر خطة (نقدر نسيبها كما هي لو تحب)
                for k, v in defaults.items():
                    try:
                        setattr(aw, k, v)
                    except Exception:
                        pass
                aw.save()
                touched += 1

                dups = qs.exclude(id=aw.id)
                if dups.exists():
                    for e in dups:
                        # دمج عدادات لو موديلك يحتويها
                        if hasattr(aw, 'total_visits') and hasattr(e, 'total_visits'):
                            aw.total_visits = (aw.total_visits or 0) + (e.total_visits or 0)
                        if hasattr(aw, 'unique_clients') and hasattr(e, 'unique_clients'):
                            aw.unique_clients = (aw.unique_clients or 0) + (e.unique_clients or 0)
                        e.delete()
                    aw.save()
                    merged += 1

    return JsonResponse({'ok': True, 'created': created, 'merged': merged, 'touched': touched})