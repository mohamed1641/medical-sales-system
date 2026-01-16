from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from urllib.parse import urlencode
import csv

from .models import DailyVisit
from plans.models import WeeklyPlan
from archives.models import ArchiveWeekly


def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


def _week_choices_for_user(user, wk_filter=None):
    """
    نعرض فقط الأسابيع الموجودة في WeeklyPlan بحالة approved (حتى لو الخطة متأرشفة).
    """
    qs = WeeklyPlan.objects.filter(status='approved')
    if not is_manager(user):
        qs = qs.filter(rep=user)
    # مهم: لا تفلتر is_deleted هنا
    if wk_filter and str(wk_filter).isdigit():
        qs = qs.filter(week_number=int(wk_filter))
    return sorted(qs.values_list('week_number', flat=True).distinct())


@login_required
def daily_view(request):
    mgr = is_manager(request.user)

    # Params
    show = (request.GET.get('show') or 'active').strip().lower()   # active | deleted | all
    q    = (request.GET.get('q') or '').strip()
    wk   = (request.GET.get('week') or '').strip()

    # Base queryset
    qs = DailyVisit.objects.select_related('rep', 'client', 'weekly_plan') \
                           .order_by('-visit_date', '-id')
    if not mgr:
        qs = qs.filter(rep=request.user)

    # Deleted filter
    if show == 'deleted':
        qs = qs.filter(is_deleted=True)
    elif show == 'all':
        pass
    else:
        qs = qs.filter(is_deleted=False)

    # Week filter
    if wk.isdigit():
        qs = qs.filter(week_number=int(wk))

    # Search
    if q:
        qs = qs.filter(
            Q(entity__icontains=q) |
            Q(client_doctor__icontains=q) |
            Q(address__icontains=q) |
            Q(city__icontains=q) |
            Q(phone__icontains=q) |
            Q(visit_objective__icontains=q) |
            Q(other_objective__icontains=q)
        )

    # Approved weekly plans التي يمكن البدء منها (بدون sync)
    approved_plans = WeeklyPlan.objects.filter(status='approved')
    if not mgr:
        approved_plans = approved_plans.filter(rep=request.user)
    if wk.isdigit():
        approved_plans = approved_plans.filter(week_number=int(wk))

    # استبعاد الخطط اللي تم اختيارها
    approved_plans = approved_plans.exclude(id__in=qs.values('weekly_plan_id'))

    # Week choices للـ UI (جاية من WeeklyPlan approved)
    week_choices = _week_choices_for_user(request.user)
    current_week = wk if wk.isdigit() else (str(week_choices[-1]) if week_choices else '')

    # Export CSV
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="daily_visits.csv"'
        w = csv.writer(resp)
        w.writerow([
            'ID','Week #','Visit Date','Actual DateTime','Entity','Doctor',
            'Address','City','Phone','Objective','Other','Rep','Created'
        ])
        for v in qs:
            w.writerow([
                v.id,
                v.week_number or '',
                v.visit_date or '',
                v.actual_datetime or '',
                v.entity or (getattr(v.client, 'entity_name', '') if v.client_id else ''),
                v.client_doctor or (getattr(v.client, 'doctor_name', '') if v.client_id else ''),
                v.address or (getattr(v.client, 'location', '') if v.client_id else ''),
                v.city or (getattr(v.client, 'city', '') if v.client_id else ''),
                v.phone or (getattr(v.client, 'phone', '') if v.client_id else ''),
                v.visit_objective or '',
                v.other_objective or '',
                (v.rep.get_full_name() or v.rep.username) if v.rep_id else '',
                v.created_at or '',
            ])
        return resp

    return render(request, 'visits/daily.html', {
        'visits': qs,
        'show': show,
        'q': q,
        'week': wk,
        'week_choices': week_choices,
        'current_week': current_week,
        'approved_plans': approved_plans,
        'mgr': mgr,
    })

    return render(request, 'visits/daily.html', {
        'visits': qs,
        'show': show,
        'q': q,
        'week': wk,
        'week_choices': week_choices,
        'current_week': current_week,
        'approved_plans': approved_plans,
        'mgr': mgr,
    })


@login_required
def start_from_weekly(request, pk):
    """
    1:1 بين WeeklyPlan (approved) و DailyVisit.
    لو الزيارة موجودة بالفعل لنفس الخطة → افتحها بدل ما تعمل واحدة جديدة.
    كذلك نتعامل مع تكرار ArchiveWeekly بأمان.
    """
    if is_manager(request.user):
        messages.error(request, 'Only Reps can start from a weekly plan.')
        return redirect('visits:daily')

    p = get_object_or_404(WeeklyPlan, pk=pk, rep=request.user, status='approved')

    # --- تأكيد وجود سجل أرشيف واحد فقط لهذا الأسبوع/المندوب ---
    try:
        aw_first = ArchiveWeekly.objects.filter(rep=request.user, week_no=p.week_number).order_by('id').first()
        if aw_first is None:
            # مفيش أرشيف: أنشئ صف بسيط (تفاصيل إضافية اختيارية)
            ArchiveWeekly.objects.create(rep=request.user, week_no=p.week_number)
        else:
            # لو فيه دوبلكيت، ادمج العدادات واحذف الزيادة
            extras = ArchiveWeekly.objects.filter(rep=request.user, week_no=p.week_number).exclude(id=aw_first.id)
            if extras.exists():
                for e in extras:
                    if hasattr(aw_first, 'total_visits') and hasattr(e, 'total_visits'):
                        aw_first.total_visits = (aw_first.total_visits or 0) + (e.total_visits or 0)
                    if hasattr(aw_first, 'unique_clients') and hasattr(e, 'unique_clients'):
                        aw_first.unique_clients = (aw_first.unique_clients or 0) + (e.unique_clients or 0)
                    e.delete()
                try:
                    aw_first.save()
                except Exception:
                    pass
    except Exception:
        # أي خطأ في الأرشيف لا يمنع إنشاء الزيارة
        pass

    # --- إنشاء/استرجاع الزيارة 1:1 مع الخطة ---
    dv, created = DailyVisit.objects.get_or_create(
        rep=request.user,
        weekly_plan=p,
        defaults={
            'week_number'    : p.week_number,
            'visit_date'     : p.planned_date or timezone.localdate(),
            'entity'         : (p.entity_address or '—').strip(),
            'address'        : (p.entity_address or '').strip(),
            'city'           : '',
            'phone'          : '',
            'client_doctor'  : '',
            'visit_objective': p.visit_objective or '',
            'other_objective': p.other_objective or '',
            'time_shift'     : '',
            'is_deleted'     : False,
        }
    )

    # لو فيه نسخة محذوفة قديمة لنفس الخطة، رجّعها بدل إنشاء زيارات جديدة
    if not created and getattr(dv, 'is_deleted', False):
        dv.is_deleted = False
        dv.save(update_fields=['is_deleted'])

    return redirect(f"/visits/?week={p.week_number}&edit={dv.id}")


@login_required
def move_to_client(request, pk):
    """
    ينقل الزيارة إلى صفحة Clients مع تمرير week ثابت وبيانات prefill.
    """
    if request.method != 'POST':
        return redirect('visits:daily')

    dv = get_object_or_404(DailyVisit, pk=pk, is_deleted=False)
    if not is_manager(request.user) and dv.rep_id != request.user.id:
        messages.error(request, 'Not allowed.')
        return redirect('visits:daily')

    params = {
        'week': dv.week_number or '',
        'doctor_name': (dv.client_doctor or '').strip(),
        'entity_name': (dv.entity or '').strip(),
        'city': (dv.city or '').strip(),
        'phone': (dv.phone or '').strip(),
        'from_visit': dv.id,
        'weekly_plan_id': dv.weekly_plan_id or '',  # أضفنا الـ weekly_plan_id
    }
    qs = urlencode({k: v for k, v in params.items() if v})
    url = "/clients/"
    if qs:
        url += f"?{qs}"
    return redirect(url)
