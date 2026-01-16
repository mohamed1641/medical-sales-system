from datetime import date, timedelta
from collections import defaultdict
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from visits.models import DailyVisit
from plans.models import WeeklyPlan
from reps.models import RepProfile
from clientsapp.models import Client

def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()

@login_required
@user_passes_test(is_manager)
def main(request):
    # ----- المدى الزمني -----
    rng = request.GET.get('range') or '30'
    today = timezone.localdate()
    if rng == 'all':
        start = date(1970, 1, 1)
    else:
        try:
            days = int(rng)
        except ValueError:
            days = 30
        start = today - timedelta(days=days)

    # ----- كشف أسماء الحقول المتاحة في DailyVisit لتوافق الفروع -----
    dv_fields = {f.name for f in DailyVisit._meta.get_fields()}
    if 'actual_datetime' in dv_fields:
        date_field = 'actual_datetime'
        range_filter = {f'{date_field}__date__gte': start}
        order_expr = f'-{date_field}'
    else:
        date_field = 'visit_date'
        range_filter = {f'{date_field}__gte': start}
        order_expr = f'-{date_field}'

    # ----- كويري المدى -----
    dv_range = DailyVisit.objects.filter(**range_filter)

    # ----- KPIs -----
    total = dv_range.count()
    approved = WeeklyPlan.objects.filter(
        planned_date__gte=start, status__iexact='Approved'
    ).count()

    deals_q = Q()
    if 'visit_objective' in dv_fields:
        deals_q |= Q(visit_objective__iexact='Deal Closed')
    if 'visit_status' in dv_fields:
        deals_q |= Q(visit_status__iexact='Deal Closed')
    deals = dv_range.filter(deals_q).count() if ('visit_status' in dv_fields or 'visit_objective' in dv_fields) else 0

    active_reps = RepProfile.objects.filter(user__is_active=True).count()
    clients_count = Client.objects.filter(is_deleted=False).count()

    upcoming_q = WeeklyPlan.objects.filter(
        planned_date__gte=today,
        planned_date__lte=today + timedelta(days=7),
        status__iexact='Approved'
    ).count()

    conversion = round((deals / total) * 100) if total else 0

    # ----- Visits by Rep (Bar) -----
    rep_rows = (
        dv_range.values('rep__first_name', 'rep__last_name', 'rep__username')
                .annotate(c=Count('id'))
                .order_by('-c')
    )
    by_rep = []
    by_rep_total = 0
    for r in rep_rows:
        name = f"{(r.get('rep__first_name') or '').strip()} {(r.get('rep__last_name') or '').strip()}".strip()
        if not name:
            name = r.get('rep__username') or '—'
        count = r['c']
        by_rep_total += count
        by_rep.append({'label': name, 'count': count})

    # ----- Monthly Trend (آخر 12 شهر) -----
    start_12 = today.replace(day=1) - timedelta(days=365)
    dv12 = DailyVisit.objects.filter(**{f'{date_field}__gte': start_12})
    trend_visits, trend_deals = defaultdict(int), defaultdict(int)

    for row in dv12.values(date_field, 'visit_status', 'visit_objective'):
        dt = row.get(date_field)
        if hasattr(dt, 'date'):
            dt = dt.date()
        key = f'{dt.year}-{dt.month:02d}'
        trend_visits[key] += 1
        status_val = (row.get('visit_status') or '').lower()
        obj_val = (row.get('visit_objective') or '').lower()
        if status_val == 'deal closed' or obj_val == 'deal closed':
            trend_deals[key] += 1

    months = []
    cur = today.replace(day=1)
    for _ in range(12):
        months.append(f'{cur.year}-{cur.month:02d}')
        if cur.month == 1:
            cur = cur.replace(year=cur.year - 1, month=12)
        else:
            cur = cur.replace(month=cur.month - 1)
    months.reverse()

    trend = {
        'labels': months,
        'visits': [trend_visits.get(m, 0) for m in months],
        'deals':  [trend_deals.get(m, 0) for m in months],
    }

    # ----- Recent Daily Visits -----
    recent_q = dv_range.order_by(order_expr)[:10]
    recent = []
    for v in recent_q:
        rep_name = getattr(v, 'rep', None)
        rep_name = (rep_name.get_full_name() or rep_name.username) if rep_name else '—'
        dt_val = getattr(v, date_field, None)
        dt_str = dt_val.strftime('%Y-%m-%d %H:%M') if hasattr(dt_val, 'strftime') else str(dt_val)
        account = getattr(v, 'entity', '') or (getattr(v, 'client', None).entity_name if getattr(v, 'client_id', None) else '')
        doctor = getattr(v, 'client_doctor', '') or (getattr(v, 'client', None).doctor_name if getattr(v, 'client_id', None) else '')
        outcome = (getattr(v, 'visit_status', '') or getattr(v, 'visit_objective', '') or '')

        recent.append({
            'dt': dt_str,
            'rep': rep_name,
            'account': account,
            'doctor': doctor,
            'outcome': outcome,
        })

    # ----- Next 7 days (Approved Weekly) -----
    upcoming_rows = WeeklyPlan.objects.filter(
        planned_date__gte=today,
        planned_date__lte=today + timedelta(days=7),
        status__iexact='Approved'
    ).order_by('planned_date')[:10]

    upcoming = []
    for p in upcoming_rows:
        rep_name = getattr(p, 'rep', None)
        rep_name = (rep_name.get_full_name() or rep_name.username) if rep_name else '—'
        plan_txt = getattr(p, 'aa_plan', None) or getattr(p, 'weekly_plan', None) or ''
        obj_txt = getattr(p, 'visit_objective', None) or ''
        upcoming.append({
            'date': p.planned_date,
            'rep': rep_name,
            'plan': plan_txt,
            'obj': obj_txt
        })

    dash = {
        'kpis': {
            'total': total,
            'approved': approved,
            'deals': deals,
            'reps': active_reps,
            'clients': clients_count,
            'upcoming': upcoming_q,
            'conversion': conversion,
            'by_rep_total': by_rep_total,
        },
        'by_rep': by_rep,
        'trend': trend,
        'recent': recent,
        'upcoming': upcoming,
    }

    return render(request, 'dashboard/main.html', {'dash': dash, 'range': rng})
