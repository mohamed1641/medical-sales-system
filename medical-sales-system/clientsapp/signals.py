# clientsapp/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Client
from plans.models import WeeklyPlan
from visits.models import DailyVisit

try:
    from archives.models import ArchiveWeekly
except Exception:
    ArchiveWeekly = None

User = get_user_model()

DONE_STATES = {'done','completed','finished','closed','visited','success','ok','تم','منجز','منتهي','مكتمل'}

def _get_week_number(obj):
    return getattr(obj, 'week_number', None) or getattr(obj, 'week_no', None)

def _upsert_archive_weekly_snapshot(wp):
    if ArchiveWeekly is None or wp is None:
        return
    week_val = _get_week_number(wp)
    total_visits = DailyVisit.objects.filter(weekly_plan_id=wp.id).count()
    unique_clients = DailyVisit.objects.filter(weekly_plan_id=wp.id).values('client_id').distinct().count()
    # نحاول أكثر من شكل حقول
    candidates = [
        ({"week_no": week_val, "plan": wp}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        ({"week_no": week_val}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        ({"week_number": week_val, "plan": wp}, {"total_visits": total_visits, "unique_clients": unique_clients}),
        ({"week_number": week_val}, {"total_visits": total_visits, "unique_clients": unique_clients}),
    ]
    from django.core.exceptions import FieldError
    for where, defaults in candidates:
        try:
            ArchiveWeekly.objects.update_or_create(**where, defaults=defaults)
            return
        except FieldError:
            continue
        except Exception:
            return

@receiver(post_save, sender=Client)
def finalize_triplet_after_client_save(sender, instance: Client, created, **kwargs):
    """
    أوتوماتك: بمجرد ما العميل يتسجّل/يتحدّث ومعاه week_number + rep،
    نلاقي الـ WeeklyPlan الموافق ونأرشف:
      - كل DailyVisit بتاعة نفس الخطة
      - الخطة WeeklyPlan نفسها
      - العميل Client نفسه
    ونرمي Snapshot في ArchiveWeekly.
    """
    rep = getattr(instance, 'rep', None)
    wk = _get_week_number(instance)
    if not (rep and wk):
        return

    # هات الخطة الموافقه (أفضل Approved وغير مؤرشفة)
    wp = WeeklyPlan.objects.filter(rep=rep, week_number=wk, status__iexact='approved', is_deleted=False).order_by('-id').first()
    if not wp:
        return

    now = timezone.now()

    # أرشفة كل زيارات الأسبوع المرتبطة بالخطة
    daily_qs = DailyVisit.objects.filter(weekly_plan=wp, is_deleted=False)
    for v in daily_qs:
        v.is_deleted = True
        if hasattr(v, 'deleted_at'): v.deleted_at = now
        if hasattr(v, 'deleted_by'): v.deleted_by = rep
        v.last_change = f"{now:%Y-%m-%d %H:%M} — auto-archived via client save"
        try:
            v.save(update_fields=['is_deleted','deleted_at','deleted_by','last_change','updated_at'])
        except Exception:
            v.save()

    # أرشفة الخطة نفسها
    if hasattr(wp, 'is_deleted') and not wp.is_deleted:
        wp.is_deleted = True
        if hasattr(wp, 'deleted_at'): wp.deleted_at = now
        if hasattr(wp, 'deleted_by'): wp.deleted_by = rep
        try:
            wp.save(update_fields=['is_deleted','deleted_at','deleted_by'])
        except Exception:
            wp.save()

    # أرشفة العميل نفسه (علشان يختفي من clients ويظهر فقط عبر Accounts)
    if hasattr(instance, 'is_deleted') and not instance.is_deleted:
        instance.is_deleted = True
        if hasattr(instance, 'deleted_at'): instance.deleted_at = now
        if hasattr(instance, 'deleted_by'): instance.deleted_by = rep
        try:
            instance.save(update_fields=['is_deleted','deleted_at','deleted_by'])
        except Exception:
            instance.save()

    # Snapshot في الأرشيف
    _upsert_archive_weekly_snapshot(wp)
