# archives/utils.py
from django.db.models import Count
from django.utils import timezone

from plans.models import WeeklyPlan
from visits.models import DailyVisit
from clientsapp.models import Client
from .models import ArchiveWeekly

def _get_week_value(wp, fallback_week_no):
    # wp.week_number أو wp.week_no
    return getattr(wp, 'week_number', None) or getattr(wp, 'week_no', None) or fallback_week_no

def finalize_week(week_no: int, rep):
    """
    يكمّل الأسبوع لو (فيه Weekly + Daily + Client) لنفس الـ Rep ونفس week_no
    - ياخد سنابشوت في ArchiveWeekly (update_or_create)
    - يعمل Soft-delete لـ DailyVisit و Client (علشان تختفي من الصفحات)
    - يغيّر حالة WeeklyPlan إلى Archived (لو عندك status)
    """
    if not week_no or not rep:
        return False

    # Weekly لنفس الأسبوع ونفس الـ Rep
    wp_qs = WeeklyPlan.objects.filter(rep=rep).all()
    wp_qs = [wp for wp in wp_qs if _get_week_value(wp, None) == week_no]
    if not wp_qs:
        return False

    dv_qs = DailyVisit.objects.filter(rep=rep, week_number=week_no, is_deleted=False)
    cl_qs = Client.objects.filter(rep=rep, week_number=week_no, is_deleted=False)

    if not dv_qs.exists() or not cl_qs.exists():
        # لسه مش جاهز للأرشفة
        return False

    # ناخد أول Weekly كمرجع لحقول العرض
    wp = sorted(wp_qs, key=lambda x: (getattr(x, 'planned_date', None) or timezone.localdate()))[0]

    defaults = {
        'planned_date': getattr(wp, 'planned_date', None),
        'aa_plan': getattr(wp, 'aa_plan', '') or getattr(wp, 'plan_text', '') or '',
        'targeted_line': getattr(wp, 'product_line', '') or '',
        'entity_type': getattr(wp, 'entity_type', '') or '',
        'specialization': getattr(wp, 'specialization', '') or '',
        'visit_objective': getattr(wp, 'visit_objective', '') or '',
        'entity_address': getattr(wp, 'entity_address', '') or '',
        'notes': getattr(wp, 'notes', '') or '',
        'status': 'Completed',
        'total_visits': dv_qs.count(),
        'unique_clients': dv_qs.values('client_id', 'entity').distinct().count(),
    }

    ArchiveWeekly.objects.update_or_create(
        week_no=week_no, rep=rep, defaults=defaults
    )

    # Soft-delete: تختفي من الصفحات
    now = timezone.now()
    dv_qs.update(is_deleted=True, deleted_at=now, deleted_by=rep)
    cl_qs.update(is_deleted=True, deleted_at=now, deleted_by=rep)

    # Weekly: علّمه مؤرشف (لو عندك status)
    if hasattr(WeeklyPlan, 'status'):
        WeeklyPlan.objects.filter(rep=rep).filter(
            # دعم week_number و week_no
            **({'week_number': week_no} if hasattr(WeeklyPlan, 'week_number') else {'week_no': week_no})
        ).update(status='Archived')

    return True
