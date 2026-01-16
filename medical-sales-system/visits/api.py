from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.exceptions import FieldError

from .models import DailyVisit
from plans.models import WeeklyPlan

# محاولة استيراد موديل الأرشيف إن وُجد
try:
    from archives.models import ArchiveWeekly
except Exception:
    ArchiveWeekly = None


# ============================
# Helpers — أرشفة تلقائية
# ============================

def _is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


def _serialize_visit(v):
    return {
        "id": v.id,
        "entity": getattr(v, "entity", "") or getattr(v, "visited_account", ""),
        "actual_datetime": getattr(v, "actual_datetime", None),
        "time_shift": getattr(v, "time_shift", ""),
        "doctor_name": getattr(v, "doctor_name", ""),
        "phone": getattr(v, "phone", "") or getattr(v, "phone_number", ""),
        "rep_id": getattr(v, "rep_id", None),
        "rep": (v.rep.get_full_name() or v.rep.username) if getattr(v, "rep", None) else "",
        "visit_outcome": getattr(v, "visit_outcome", "") or getattr(v, "visit_objective", ""),
        "additional_outcome": getattr(v, "additional_outcome", "") or getattr(v, "other_objective", ""),
        "visit_status": getattr(v, "visit_status", "") or getattr(v, "status", ""),
        "weekly_plan_id": getattr(v, "weekly_plan_id", None),
        "client_doctor": getattr(v, "client_doctor", "") or (
            getattr(v, "client", None) and getattr(v.client, "doctor_name", "") or ""
        ),
        "address": getattr(v, "address", ""),
        "city": getattr(v, "city", ""),
        "is_deleted": getattr(v, "is_deleted", False),
        "last_change": getattr(v, "last_change", "") or "",
        "created_at": getattr(v, "created_at", None),
        "updated_at": getattr(v, "updated_at", None),
    }


def _get_week_number_from_weekly(wp):
    """يدعم week_number أو week_no."""
    return getattr(wp, 'week_number', None) or getattr(wp, 'week_no', None)


def _upsert_archive_weekly_snapshot(wp):
    """
    محاولة إنشاء/تحديث سنابشوت في ArchiveWeekly بشكل مرن.
    لو الموديل/الحقول مش متوافقة، نتجاهل بصمت بدون كسر الفلو.
    """
    if ArchiveWeekly is None or wp is None:
        return

    week_val = _get_week_number_from_weekly(wp)

    # إجماليات سريعة من DailyVisit لنفس الخطة
    total_visits = DailyVisit.objects.filter(weekly_plan_id=wp.id).count()
    total_archived = DailyVisit.objects.filter(weekly_plan_id=wp.id, is_deleted=True).count()
    # لو عندك FK client_id في الزيارة هنعد المميّز، وإلا نخليها صفر
    try:
        unique_clients = DailyVisit.objects.filter(weekly_plan_id=wp.id).values('client_id').distinct().count()
    except Exception:
        unique_clients = 0

    # هنجرّب أكثر من شكل حقول بحيث ما نكسرش لو الاسكيمة مختلفة
    attempts = [
        # شائع: week_no فقط
        ({"week_no": week_val}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        # بديل: week_number
        ({"week_number": week_val}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        # بعض المشاريع بتحتاج plan FK
        ({"week_no": week_val, "plan": wp}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        ({"week_number": week_val, "plan": wp}, {"total_visits": total_visits, "unique_clients": unique_clients}),
    ]
    for where, defaults in attempts:
        try:
            ArchiveWeekly.objects.update_or_create(**where, defaults=defaults)
            return
        except FieldError:
            # جرّب محاولة أخرى بحقول بديلة
            continue
        except Exception:
            # لو في شرط إجباري تاني في الموديل، نتجاهل بدون كسر الأرشفة العامة
            return


def _archive_weekly_plan_if_done(weekly_plan_id, user):
    """
    لو كل زيارات الخطة اتأرشفت (is_deleted=True)، أرشف الخطة نفسها وأعمل سنابشوت في الأرشيف.
    """
    if not weekly_plan_id:
        return

    try:
        # لسه فيه زيارات نشطة؟
        still_active = DailyVisit.objects.filter(weekly_plan_id=weekly_plan_id, is_deleted=False).exists()
        if still_active:
            return

        wp = WeeklyPlan.objects.get(pk=weekly_plan_id)

        # أرشفة الخطة (لو عندها حقول soft-delete)
        if hasattr(wp, 'is_deleted') and not wp.is_deleted:
            wp.is_deleted = True
            if hasattr(wp, 'deleted_at'):
                wp.deleted_at = timezone.now()
            if hasattr(wp, 'deleted_by'):
                wp.deleted_by = user
            try:
                wp.save(update_fields=[f for f in ['is_deleted', 'deleted_at', 'deleted_by'] if hasattr(wp, f)])
            except Exception:
                # في حال عدم وجود update_fields
                wp.save()

        # سنابشوت في جدول الأرشيف (اختياري/مرن)
        _upsert_archive_weekly_snapshot(wp)

    except WeeklyPlan.DoesNotExist:
        return


def _auto_archive_visit_and_cascade(obj, user, reason="archived"):
    """
    أرشف الزيارة + جرّب أرشفة الخطة لو كل زياراتها اتقفلت + سنابشوت.
    """
    if not getattr(obj, 'is_deleted', False):
        obj.is_deleted = True
        if hasattr(obj, 'deleted_at'):
            obj.deleted_at = timezone.now()
        if hasattr(obj, 'deleted_by'):
            obj.deleted_by = user
        obj.last_change = f"{timezone.now():%Y-%m-%d %H:%M} — {user.username} {reason}"
        try:
            obj.save(update_fields=[f for f in ['is_deleted', 'deleted_at', 'deleted_by', 'last_change', 'updated_at'] if hasattr(obj, f)])
        except Exception:
            obj.save()

    # كاسكيد على الخطة
    _archive_weekly_plan_if_done(getattr(obj, 'weekly_plan_id', None), user)


def _is_done_status(val):
    """
    تعريف الحالات التي نعتبرها "منتهية" وتستحق الأرشفة الآلية.
    تقدر تزود أو تقلل حسب نظامك.
    """
    if not val:
        return False
    v = str(val).strip().lower()
    return v in {
        'done', 'completed', 'finished', 'closed',
        'تم', 'منجز', 'منتهي', 'مكتمل',
        'visited', 'success', 'ok'
    }


# ============================
# API Endpoints
# ============================

@login_required
@require_GET
def api_list(request):
    """List + search + simple paging (JSON). Supports ?show=deleted/all (manager only)."""
    q = (request.GET.get("q") or "").strip()
    date_str = (request.GET.get("date") or "").strip()
    size = int(request.GET.get("size") or request.GET.get("page_size") or 20)
    page = int(request.GET.get("page") or 1)
    show = (request.GET.get("show") or "").strip().lower()

    qs = DailyVisit.objects.select_related("rep", "client", "weekly_plan").order_by("-actual_datetime", "-id")

    # إخفاء المؤرشف/المحذوف افتراضيًا
    if _is_manager(request.user):
        if show == "deleted":
            qs = qs.filter(is_deleted=True)
        elif show == "all":
            pass
        else:
            qs = qs.filter(is_deleted=False)
    else:
        qs = qs.filter(is_deleted=False)

    # Rep يشوف زياراته فقط
    if not _is_manager(request.user):
        qs = qs.filter(rep=request.user)

    if q:
        qs = qs.filter(
            Q(entity__icontains=q) | Q(visited_account__icontains=q) |
            Q(doctor_name__icontains=q) | Q(phone__icontains=q) |
            Q(visit_outcome__icontains=q) | Q(visit_objective__icontains=q) |
            Q(additional_outcome__icontains=q) | Q(other_objective__icontains=q) |
            Q(address__icontains=q) | Q(city__icontains=q) |
            Q(client_doctor__icontains=q)
        )

    if date_str:
        d = parse_date(date_str)
        if d:
            qs = qs.filter(Q(actual_datetime__date=d) | Q(visit_date=d))

    total = qs.count()
    start = (page - 1) * size
    rows = [_serialize_visit(v) for v in qs[start:start + size]]
    return JsonResponse({"total": total, "page": page, "size": size, "rows": rows})


@login_required
@require_POST
def api_save(request):
    """
    Create/Update DailyVisit.
    - Rep ما يقدرش يغيّر rep_id (المدير فقط).
    - لازم الريب يربط الزيارة بـ WeeklyPlan Approved بتاعه.
    - last_change بتتحدث تلقائيًا عند التعديل.
    - NEW: أرشفة تلقائية لو الحالة أصبحت منتهية أو لو تبعت archive/mark_done.
    """
    data = request.POST

    def pick(*names):
        for n in names:
            v = data.get(n)
            if v not in (None, ''):
                return v
        return None

    vid = data.get("id")
    creating = False
    if vid:
        try:
            obj = DailyVisit.objects.select_related("rep").get(pk=vid)
        except DailyVisit.DoesNotExist:
            return HttpResponseBadRequest("Visit not found")
        if not _is_manager(request.user) and obj.rep_id != request.user.id:
            return HttpResponseBadRequest("Not allowed")

        # snapshot old values
        def old_get(key):
            if key == "visit_outcome":
                return getattr(obj, "visit_outcome", None) or getattr(obj, "visit_objective", None)
            if key == "additional_outcome":
                return getattr(obj, "additional_outcome", None) or getattr(obj, "other_objective", None)
            if key == "weekly_plan_id":
                return getattr(obj, "weekly_plan_id", None)
            return getattr(obj, key, None)

        old_vals = {
            "entity": old_get("entity"),
            "actual_datetime": old_get("actual_datetime"),
            "time_shift": old_get("time_shift"),
            "doctor_name": old_get("doctor_name"),
            "phone": old_get("phone"),
            "visit_outcome": old_get("visit_outcome"),
            "additional_outcome": old_get("additional_outcome"),
            "visit_status": old_get("visit_status"),
            "weekly_plan_id": old_get("weekly_plan_id"),
            "client_doctor": old_get("client_doctor"),
        }
    else:
        obj = DailyVisit()
        creating = True

    # -------- binding آمن بأسماء بديلة --------
    ent = pick("visited_account", "entity", "account", "hospital", "clinic")
    if ent is not None:
        obj.entity = ent

    # actual_datetime (+ visit_date auto)
    dt_str = pick("actual_datetime", "actual_visit_datetime", "visit_datetime", "datetime", "date_time")
    if dt_str:
        dt = parse_datetime(dt_str)
        if dt:
            obj.actual_datetime = dt
            if not getattr(obj, "visit_date", None):
                obj.visit_date = dt.date()

    vd_str = pick("visit_date")
    if vd_str:
        try:
            obj.visit_date = parse_date(vd_str)
        except Exception:
            pass

    ts = pick("time_shift", "timeshift", "time_slot", "shift", "shift_time")
    if ts is not None and hasattr(obj, "time_shift"):
        obj.time_shift = ts

    dr = pick("doctor_name", "doctor", "dr_name", "doc_name")
    if dr is not None and hasattr(obj, "doctor_name"):
        obj.doctor_name = dr

    ph = pick("phone", "phone_number", "mobile")
    if ph is not None:
        if hasattr(obj, "phone"): obj.phone = ph
        elif hasattr(obj, "phone_number"): obj.phone_number = ph

    outcome = pick("visit_outcome", "outcome", "result", "visit_result")
    if outcome is not None:
        if hasattr(obj, "visit_outcome"): obj.visit_outcome = outcome
        if hasattr(obj, "visit_objective"): obj.visit_objective = outcome

    add_out = pick("additional_outcome", "other_objective", "notes", "remarks", "desc", "description")
    if add_out is not None:
        if hasattr(obj, "additional_outcome"): obj.additional_outcome = add_out
        elif hasattr(obj, "other_objective"): obj.other_objective = add_out

    st = pick("visit_status", "status", "state")
    if st is not None:
        if hasattr(obj, "visit_status"): obj.visit_status = st
        elif hasattr(obj, "status"): obj.status = st

    addr = pick("address", "entity_address", "location", "addr")
    if addr is not None and hasattr(obj, "address"):
        obj.address = addr

    city = pick("city", "town", "governorate")
    if city is not None and hasattr(obj, "city"):
        obj.city = city

    cdoc = pick("client_doctor", "doctor_client", "client_doctor_name")
    if cdoc is not None and hasattr(obj, "client_doctor"):
        obj.client_doctor = cdoc

    # weekly plan — id مباشرة
    wp_id = pick("weekly_plan_id", "weekly_plan", "plan", "wp_id", "plan_id")
    if wp_id and hasattr(obj, "weekly_plan_id"):
        try:
            obj.weekly_plan_id = int(wp_id)
        except Exception:
            obj.weekly_plan_id = None
    elif hasattr(obj, "weekly_plan_id"):
        obj.weekly_plan_id = None

    # client FK (اختياري)
    client_id = pick("client_id", "client", "client_pk")
    if client_id and hasattr(obj, "client_id"):
        try:
            from clientsapp.models import Client
            obj.client = Client.objects.get(pk=int(client_id))
        except Exception:
            pass

    # rep assign
    rep_pk = pick("rep", "rep_id", "user", "user_id")
    if _is_manager(request.user) and rep_pk:
        try:
            obj.rep = User.objects.get(pk=int(rep_pk))
        except Exception:
            obj.rep = request.user
    else:
        obj.rep = request.user

    # ---------- فاليديشن: WeeklyPlan Approved لنفس الريب ----------
    if not _is_manager(request.user):
        if not getattr(obj, 'weekly_plan_id', None):
            return HttpResponseBadRequest("Weekly plan is required")
        ok = WeeklyPlan.objects.filter(
            id=obj.weekly_plan_id,
            rep=request.user,
            status__iexact='approved'
        ).exists()
        if not ok:
            return HttpResponseBadRequest("Invalid weekly plan (must be your approved plan)")

        # (اختياري) تحقق من week_no لو جاي من الفورم:
        wkno = request.POST.get('week_no')
        if wkno and str(wkno).isdigit():
            ok2 = WeeklyPlan.objects.filter(
                id=obj.weekly_plan_id,
                rep=request.user,
                status__iexact='approved',
                week_no=int(wkno)
            ).exists()
            if not ok2:
                return HttpResponseBadRequest("Weekly plan does not match selected week")

    # ---------- last_change ----------
    if creating:
        obj.last_modified_by = request.user
        obj.last_change = f"{timezone.now():%Y-%m-%d %H:%M} — {request.user.username} created"
    else:
        labels = {
            "entity": "Visited Account",
            "actual_datetime": "Actual DateTime",
            "time_shift": "Time Shift",
            "doctor_name": "Doctor Name",
            "phone": "Phone",
            "visit_outcome": "Visit Outcome",
            "additional_outcome": "Additional Outcome",
            "visit_status": "Visit Status",
            "weekly_plan_id": "Weekly Plan",
            "client_doctor": "Client (Doctor)",
        }
        new_vals = {
            "entity": getattr(obj, "entity", None),
            "actual_datetime": getattr(obj, "actual_datetime", None),
            "time_shift": getattr(obj, "time_shift", None),
            "doctor_name": getattr(obj, "doctor_name", None),
            "phone": getattr(obj, "phone", None) or getattr(obj, "phone_number", None),
            "visit_outcome": getattr(obj, "visit_outcome", None) or getattr(obj, "visit_objective", None),
            "additional_outcome": getattr(obj, "additional_outcome", None) or getattr(obj, "other_objective", None),
            "visit_status": getattr(obj, "visit_status", None) or getattr(obj, "status", None),
            "weekly_plan_id": getattr(obj, "weekly_plan_id", None),
            "client_doctor": getattr(obj, "client_doctor", None),
        }
        diffs = []
        for k, oldv in old_vals.items():
            newv = new_vals.get(k)
            if (oldv or "") != (newv or ""):
                diffs.append(f"{labels[k]}: {oldv or '—'} → {newv or '—'}")
        if diffs:
            obj.last_modified_by = request.user
            obj.last_change = f"{timezone.now():%Y-%m-%d %H:%M} — {request.user.username} edited | " + "; ".join(diffs)

    # حفظ الزيارة أولاً
    obj.save()

    # ====== NEW: أرشفة تلقائية على مستوى النظام ======
    # 1) لو اتبعت archive/mark_done صراحة
    must_archive_flag = (request.POST.get('archive') == '1') or (request.POST.get('mark_done') == '1')

    # 2) أو لو حالة الزيارة أصبحت منتهية
    final_status = getattr(obj, "visit_status", None) or getattr(obj, "status", None)
    must_archive_status = _is_done_status(final_status)

    if must_archive_flag or must_archive_status:
        _auto_archive_visit_and_cascade(obj, request.user, reason="auto-archived via save")

    return JsonResponse({"ok": True, "row": _serialize_visit(obj)})


@login_required
@require_POST
def api_archive(request, pk):
    """
    أرشفة زيارة: تختفي من القوائم (للريب والمدير) وتدخل في الأرشيف (عرضها بـ ?show=deleted).
    NEW: بعد الأرشفة، لو كل زيارات الخطة خلصت ⇒ أرشِف الخطة واعمل سنابشوت.
    """
    try:
        obj = DailyVisit.objects.get(pk=pk)
    except DailyVisit.DoesNotExist:
        return HttpResponseBadRequest("Visit not found")

    # الريب يقدر يأرشف زياراته؛ المدير يقدر يأرشف الكل
    if not _is_manager(request.user) and obj.rep_id != request.user.id:
        return HttpResponseBadRequest("Not allowed")

    _auto_archive_visit_and_cascade(obj, request.user, reason="archived")

    return JsonResponse({"ok": True, "archived": True, "row": _serialize_visit(obj)})


@login_required
@require_POST
def api_delete(request, pk):
    """حذف نهائي — Manager فقط."""
    if not _is_manager(request.user):
        return HttpResponseBadRequest("Not allowed")

    try:
        obj = DailyVisit.objects.get(pk=pk)
    except DailyVisit.DoesNotExist:
        return HttpResponseBadRequest("Visit not found")

    obj.delete()
    return JsonResponse({"ok": True})
