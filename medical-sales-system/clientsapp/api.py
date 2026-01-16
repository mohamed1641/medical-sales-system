# clientsapp/api.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Q
from .models import Client
from plans.models import WeeklyPlan
from visits.models import DailyVisit

def _is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()

@login_required
@require_GET
def api_list(request):
    """قائمة العملاء (تخفي المؤرشف افتراضياً). ?show=archived/all للمدير."""
    q    = (request.GET.get('q') or '').strip()
    show = (request.GET.get('show') or '').strip().lower()
    qs = Client.objects.order_by('-id')

    if _is_manager(request.user):
        if show == 'archived':
            qs = qs.filter(is_deleted=True)
        elif show == 'all':
            pass
        else:
            qs = qs.filter(is_deleted=False)
    else:
        qs = qs.filter(is_deleted=False)

    if q:
        qs = qs.filter(
            Q(entity_name__icontains=q) | Q(doctor_name__icontains=q) |
            Q(phone__icontains=q) | Q(city__icontains=q)
        )

    rows = []
    for c in qs[:200]:
        rows.append({
            "id": c.id,
            "entity_name": getattr(c, 'entity_name', ''),
            "doctor_name": getattr(c, 'doctor_name', ''),
            "phone": getattr(c, 'phone', ''),
            "city": getattr(c, 'city', ''),
            "is_deleted": c.is_deleted,
        })
    return JsonResponse({"rows": rows})

@login_required
@require_POST
def api_archive(request, pk):
    """أرشفة عميل: يختفي من clients ويظهر فقط في الأرشيف/الأكاونتس."""
    try:
        obj = Client.objects.get(pk=pk)
    except Client.DoesNotExist:
        return HttpResponseBadRequest("Client not found")

    # الريب/المدير الاتنين يقدروا يأرشفوا
    obj.is_deleted = True
    obj.deleted_at = timezone.now()
    obj.deleted_by = request.user
    obj.save(update_fields=['is_deleted','deleted_at','deleted_by'])
    return JsonResponse({"ok": True, "archived": True})

@login_required
@require_POST
def api_finalize(request):
    """
    Finalize تسك واحد: يأرشف Client + WeeklyPlan + DailyVisit سوا.
    يتوقع POST فيه: client_id, weekly_plan_id, daily_visit_id
    """
    cid = request.POST.get('client_id')
    pid = request.POST.get('weekly_plan_id')
    vid = request.POST.get('daily_visit_id')

    if not (cid and pid and vid):
        return HttpResponseBadRequest("client_id, weekly_plan_id, daily_visit_id are required")

    try:
        c = Client.objects.get(pk=int(cid))
    except Exception:
        return HttpResponseBadRequest("Client not found")

    try:
        p = WeeklyPlan.objects.get(pk=int(pid))
    except Exception:
        return HttpResponseBadRequest("Weekly plan not found")

    try:
        v = DailyVisit.objects.get(pk=int(vid))
    except Exception:
        return HttpResponseBadRequest("Daily visit not found")

    # صلاحيات مبسّطة: المدير حر، الريب لازم يكون صاحب الزيارة والخطة
    from django.contrib.auth.models import User
    user = request.user
    if not _is_manager(user):
        if getattr(v, 'rep_id', None) != user.id or getattr(p, 'rep_id', None) != user.id:
            return HttpResponseBadRequest("Not allowed")

    now = timezone.now()

    # أرشفة الثلاثة
    c.is_deleted, c.deleted_at, c.deleted_by = True, now, user
    p.is_deleted, p.deleted_at, p.deleted_by = True, now, user
    v.is_deleted, v.deleted_at, v.deleted_by = True, now, user

    c.save(update_fields=['is_deleted','deleted_at','deleted_by'])
    p.save(update_fields=['is_deleted','deleted_at','deleted_by'])
    v.save(update_fields=['is_deleted','deleted_at','deleted_by'])

    return JsonResponse({"ok": True, "finalized": True})
