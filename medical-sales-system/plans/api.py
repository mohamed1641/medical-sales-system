# plans/api.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Q

from .models import WeeklyPlan


def _is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


@login_required
@require_GET
def api_weeks(request):
    """
    ترجع أرقام الأسابيع من الخطط Approved وغير مؤرشفة.
    المدير: كل الريبس. الريب: خططه فقط.
    """
    qs = WeeklyPlan.objects.filter(status='approved', is_deleted=False)
    if not _is_manager(request.user):
        qs = qs.filter(rep=request.user)

    weeks = (qs.values_list('week_number', flat=True)
               .distinct().order_by('-week_number'))
    return JsonResponse({"weeks": list(weeks)})


@login_required
@require_GET
def api_plans_by_week(request):
    """
    خطط أسبوع معيّن (Approved + غير مؤرشفة).
    param: ?week=<int>
    """
    w = request.GET.get('week')
    if not (w and str(w).isdigit()):
        return HttpResponseBadRequest("week is required")
    w = int(w)

    qs = WeeklyPlan.objects.filter(
        status='approved', is_deleted=False, week_number=w
    ).select_related('rep').order_by('-planned_date', '-id')

    if not _is_manager(request.user):
        qs = qs.filter(rep=request.user)

    rows = [{
        "id": p.id,
        "label": f"#{p.id} — {p.aa_plan} — {p.planned_date}",
        "week_number": p.week_number,
        "status": p.status,
        "rep": p.rep.get_full_name() or p.rep.username,
    } for p in qs]

    return JsonResponse({"rows": rows})


@login_required
@require_GET
def api_list(request):
    """
    لست الخطط: افتراضي يخفي المؤرشف.
    المدير: ?show=archived أو ?show=all
    دعم بحث q على aa_plan/status/week_number/rep.username
    """
    q    = (request.GET.get('q') or '').strip()
    show = (request.GET.get('show') or '').strip().lower()

    qs = WeeklyPlan.objects.select_related('rep').order_by('-planned_date', '-id')

    if _is_manager(request.user):
        if show == 'archived':
            qs = qs.filter(is_deleted=True)
        elif show == 'all':
            pass
        else:
            qs = qs.filter(is_deleted=False)
    else:
        qs = qs.filter(is_deleted=False, rep=request.user)

    if q:
        qs = qs.filter(
            Q(aa_plan__icontains=q) |
            Q(status__icontains=q) |
            Q(week_number__icontains=q) |
            Q(rep__username__icontains=q)
        )

    rows = [{
        "id": p.id,
        "aa_plan": p.aa_plan,
        "planned_date": p.planned_date,
        "product_line": p.product_line,
        "entity_type": p.entity_type,
        "specialization": p.specialization,
        "status": p.status,
        "week_number": p.week_number,
        "rep": p.rep.get_full_name() or p.rep.username,
        "is_deleted": p.is_deleted,
    } for p in qs[:200]]

    return JsonResponse({"rows": rows})


@login_required
@require_POST
def api_archive(request, pk):
    """
    أرشفة الخطة: تختفي من صفحة الـWeekly (للمدير والريب) وتظهر في الأرشيف/الأكاونتس.
    """
    try:
        obj = WeeklyPlan.objects.select_related('rep').get(pk=pk)
    except WeeklyPlan.DoesNotExist:
        return HttpResponseBadRequest("Plan not found")

    # الريب يؤرشف خطته فقط؛ المدير يؤرشف أي خطة
    if not _is_manager(request.user) and obj.rep_id != request.user.id:
        return HttpResponseBadRequest("Not allowed")

    obj.is_deleted = True
    obj.deleted_at = timezone.now()
    obj.deleted_by = request.user
    obj.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    return JsonResponse({"ok": True, "archived": True})
