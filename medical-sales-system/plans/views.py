# plans/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
import csv

from .models import WeeklyPlan
from archives.models import ArchiveWeekly  # ← لإخفاء الأسابيع المؤرشفة وإضافة السنابشوت

# ---- Helpers ----
def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


# ---- Weekly (list + create + search + export) ----
@login_required
def weekly_view(request):
    mgr = is_manager(request.user)

    # بارامترات العرض
    show = (request.GET.get('show') or 'active').strip().lower()  # active | deleted | all
    q    = (request.GET.get('q') or '').strip()
    wk   = (request.GET.get('week') or '').strip()
    hide_archived = (request.GET.get('hide_archived') or '0').strip() != '0'  # الافتراضي لا يخفي المؤرشف

    # Queryset حسب الصلاحية
    qs = WeeklyPlan.objects.select_related('rep').order_by('-planned_date', '-id')
    if not mgr:
        qs = qs.filter(rep=request.user)

    # فلتر الأرشفة/الحذف
    if hasattr(WeeklyPlan, 'is_deleted'):
        if show == 'deleted':
            qs = qs.filter(is_deleted=True)
        elif show == 'all':
            pass
        else:
            qs = qs.filter(is_deleted=False)

    # فلتر Week Number
    if wk.isdigit():
        qs = qs.filter(week_number=int(wk))

    # بحث ?q=
    if q:
        qs = qs.filter(
            Q(aa_plan__icontains=q) |
            Q(entity_address__icontains=q) |
            Q(notes__icontains=q) |
            Q(visit_objective__icontains=q) |
            Q(specialization__icontains=q) |
            Q(entity_type__icontains=q) |
            Q(product_line__icontains=q) |
            Q(rep__username__icontains=q) |
            Q(rep__first_name__icontains=q) |
            Q(rep__last_name__icontains=q)
        )

    # إخفاء الأسابيع المؤرشفة (موجودة في ArchiveWeekly) — مع إبقاء الـPending ظاهر للموافقة
    if hide_archived:
        arch = ArchiveWeekly.objects.all()
        if not mgr:
            arch = arch.filter(rep=request.user)
        if wk.isdigit():
            arch = arch.filter(week_no=int(wk))
        arch_weeks = list(arch.values_list('week_no', flat=True))
        if arch_weeks:
            qs = qs.exclude(Q(week_number__in=arch_weeks) & ~Q(status='pending'))

    # Export CSV بنفس الفلاتر الحالية
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="weekly_plans.csv"'
        w = csv.writer(resp)
        w.writerow([
            'ID','Aa Plan','Planned Date','Product Line','Entity Address','Entity Type',
            'Specialization','Notes','Visit Objective','Other Objective','Rep','Week #','Status'
        ])
        for p in qs:
            w.writerow([
                p.id, p.aa_plan, p.planned_date, p.product_line, p.entity_address, p.entity_type,
                p.specialization, p.notes, p.visit_objective,
                (p.other_objective if p.visit_objective == 'Other' else ''),
                (p.rep.get_full_name() or p.rep.username), p.week_number, p.get_status_display()
            ])
        return resp

    # POST: إنشاء Plan جديدة (الـRep دايمًا نفسه / المدير يقدر يختار من الـselect)
    if request.method == 'POST':
        data = request.POST

        # تحقق من "Other Objective"
        objective = (data.get('visit_objective') or '').strip()
        if objective == 'Other' and not (data.get('other_objective') or '').strip():
            messages.error(request, 'Please fill "Other Objective?".')
            return redirect('plans:weekly')

        # تحديد الـrep
        rep = request.user
        if mgr and data.get('rep'):
            try:
                rep = User.objects.get(id=int(data.get('rep')), is_active=True)
            except (User.DoesNotExist, ValueError):
                messages.error(request, 'Invalid Rep selected.')
                return redirect('plans:weekly')

        # رقم الأسبوع
        try:
            week_number = int(data.get('week_number') or 1)
        except ValueError:
            week_number = 1

        # إنشاء بدون أي قيود (تسمح بعدد لا نهائي لنفس الأسبوع/اليوم)
        try:
            WeeklyPlan.objects.create(
                aa_plan=(data.get('aa_plan') or '').strip(),
                planned_date=data.get('planned_date'),
                product_line=(data.get('product_line') or ''),
                entity_address=(data.get('entity_address') or '').strip(),
                entity_type=(data.get('entity_type') or ''),
                specialization=(data.get('specialization') or ''),
                notes=(data.get('notes') or '').strip(),
                visit_objective=objective,
                other_objective=((data.get('other_objective') or '').strip() if objective == 'Other' else ''),
                rep=rep,
                week_number=week_number,
                # status: الافتراضي pending من الموديل
            )
            messages.success(request, 'Weekly plan saved (Pending).')
        except Exception as e:
            messages.error(request, f'Could not save: {e}')
        return redirect('plans:weekly')

    # خيارات الـRep للسلكت
    rep_choices = (
        User.objects.filter(groups__name='Rep', is_active=True).order_by('first_name', 'username')
        if mgr else User.objects.filter(id=request.user.id)
    )

    return render(request, 'plans/weekly.html', {
        'mgr': mgr,                   # ← مهم للتمبلت
        'plans': qs,
        'rep_choices': rep_choices,
        'show': show,
        'q': q,
        'week': wk,
        'hide_archived': '1' if hide_archived else '0',
    })


# ---- Approve / Reject (Manager-only) ----
@login_required
@user_passes_test(is_manager)
@require_POST
def approve_weekly(request, pk):
    """
    عند الموافقة:
    1) نحدّث الحالة إلى approved
    2) نكتب/نحدّث ArchiveWeekly لنفس (rep, week_no) بتفاصيل الخطة
    3) نعمل Soft-delete للخطة فورًا (تختفي من النظام وتظهر فقط في الأرشيف)
    """
    plan = get_object_or_404(WeeklyPlan, pk=pk)

    # 1) تحديث الحالة
    plan.status = 'approved'
    try:
        plan.save(update_fields=['status', 'updated_at'])
    except Exception:
        plan.save()

    # 2) كتابة/تحديث الأرشيف
    defaults = {
        'planned_date'   : plan.planned_date,
        'aa_plan'        : getattr(plan, 'aa_plan', ''),
        'targeted_line'  : getattr(plan, 'product_line', ''),
        'entity_type'    : getattr(plan, 'entity_type', ''),
        'specialization' : getattr(plan, 'specialization', ''),
        'visit_objective': getattr(plan, 'visit_objective', ''),
        'entity_address' : getattr(plan, 'entity_address', ''),
        'notes'          : getattr(plan, 'notes', ''),
        'status'         : 'Approved',
        # سيزيد total_visits / unique_clients لاحقًا عند إنشاء العميل (clientsapp/views.py)
    }
    try:
        ArchiveWeekly.objects.update_or_create(
            rep=plan.rep, week_no=plan.week_number, defaults=defaults
        )
    except Exception:
        # لو فيه أي مشكلة في الأرشيف، نكمّل موافقة الخطة بس نعرض تنبيه
        messages.warning(request, 'Plan approved, but archiving snapshot failed.')

    # 3) Soft-delete للخطة فورًا
    if hasattr(plan, 'is_deleted'):
        plan.is_deleted = True
        plan.deleted_at = timezone.now()
        if hasattr(plan, 'deleted_by'):
            plan.deleted_by = plan.rep
        try:
            plan.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        except Exception:
            plan.save()

    messages.success(request, f'Plan #{plan.id} approved, archived, and hidden (Week {plan.week_number}).')
    return redirect('plans:weekly')


@login_required
@user_passes_test(is_manager)
@require_POST
def reject_weekly(request, pk):
    if request.method != 'POST':
        return redirect('plans:weekly')
    plan = get_object_or_404(WeeklyPlan, pk=pk)
    plan.status = 'rejected'
    try:
        plan.save(update_fields=['status', 'updated_at'])
    except Exception:
        plan.save()
    messages.warning(request, f'Plan #{plan.id} rejected.')
    return redirect('plans:weekly')

      # # منع تكرار Plan لنفس الـRep ونفس الأسبوع وهي Active (مع استثناء rejected)
        # dup_qs = WeeklyPlan.objects.filter(rep=rep, week_number=week_number)
        # if hasattr(WeeklyPlan, 'is_deleted'):
        #     dup_qs = dup_qs.filter(is_deleted=False)
        # if dup_qs.exclude(status='rejected').exists():
        #     messages.warning(request, f'A plan for Week {week_number} already exists for this Rep.')
        #     return redirect('plans:weekly')
