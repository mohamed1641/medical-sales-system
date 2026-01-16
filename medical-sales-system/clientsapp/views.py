# clientsapp/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.db import transaction
import csv

from .models import Client
from plans.models import WeeklyPlan
from visits.models import DailyVisit
from archives.models import ArchiveWeekly


def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


def _plans_for_week(rep, week_number):
    # Approved فقط (وغير محذوفة) لو احتجنا نعرضها في أي مكان
    qs = WeeklyPlan.objects.filter(rep=rep, week_number=week_number, status='approved')
    if hasattr(WeeklyPlan, 'is_deleted'):
        qs = qs.filter(is_deleted=False)
    return qs


@login_required
def clients_list(request):
    mgr  = is_manager(request.user)
    q    = (request.GET.get('q') or '').strip()
    wk   = (request.GET.get('week') or '').strip()
    show = (request.GET.get('show') or 'active').strip().lower()
    hide_archived = (request.GET.get('hide_archived') or '1').strip() != '0'

    # Base
    qs = Client.objects.select_related('rep').order_by('-updated_at', '-id')

    # Archive flag
    if show == 'deleted':
        qs = qs.filter(is_deleted=True)
    elif show == 'all':
        pass
    else:
        qs = qs.filter(is_deleted=False)

    # Permissions
    if not mgr:
        qs = qs.filter(rep=request.user)

    # Search
    if q:
        qs = qs.filter(
            Q(doctor_name__icontains=q) |
            Q(entity_name__icontains=q) |
            Q(city__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(status__icontains=q) |
            Q(notes__icontains=q)
        )

    # Week filter
    if wk.isdigit():
        qs = qs.filter(week_number=int(wk))

    # Hide archived weeks (present in ArchiveWeekly.week_no)
    if hide_archived:
        arch = ArchiveWeekly.objects.all()
        if not mgr:
            arch = arch.filter(rep=request.user)
        if wk.isdigit():
            arch = arch.filter(week_no=int(wk))
        arch_weeks = list(arch.values_list('week_no', flat=True))
        if arch_weeks:
            qs = qs.exclude(week_number__in=arch_weeks)

    # ---------- Dropdown: Daily Visits (غير مرتبطة بعميل) ----------
    dv_dropdown = DailyVisit.objects.filter(is_deleted=False, client__isnull=True)
    if not mgr:
        dv_dropdown = dv_dropdown.filter(rep=request.user)
    if wk.isdigit():
        dv_dropdown = dv_dropdown.filter(week_number=int(wk))
    dv_dropdown = dv_dropdown.order_by('-visit_date', '-id')

    # Export CSV
    if request.GET.get('export') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="clients.csv"'
        w = csv.writer(resp)
        w.writerow(['#','Doctor','Entity','City','Phone','Email','Status','Rep','Week #'])
        for i, c in enumerate(qs, start=1):
            w.writerow([
                i,
                c.doctor_name,
                c.entity_name,
                c.city,
                c.phone,
                c.email,
                c.status,
                (c.rep.get_full_name() or c.rep.username) if c.rep_id else '',
                c.week_number or ''
            ])
        return resp

    # ---------------------- POST (Create/Edit + ARCHIVE IMMEDIATELY) ----------------------
    if request.method == 'POST':
        data = request.POST
        cid  = data.get('id')

        # تعديل أو إنشاء
        if cid:
            try:
                obj = Client.objects.get(pk=cid)
            except Client.DoesNotExist:
                return HttpResponseBadRequest("Client not found")
            if not mgr and obj.rep_id != request.user.id:
                return HttpResponseBadRequest("Not allowed")
        else:
            obj = Client(rep=request.user)

        # لو مدير حدّد مندوب
        if mgr and data.get('rep'):
            try:
                obj.rep = User.objects.get(id=int(data.get('rep')), is_active=True)
            except Exception:
                pass

        # الزيارة اليومية (إلزامية عند الإنشاء)
        dv_id  = data.get('daily_visit')
        dv_obj = None
        if not cid:
            if not dv_id or not str(dv_id).isdigit():
                return HttpResponseBadRequest("اختَر الزيارة اليومية أولاً.")
            dv_qs = DailyVisit.objects.filter(id=int(dv_id), is_deleted=False, client__isnull=True)
            if not mgr:
                dv_qs = dv_qs.filter(rep=request.user)
            dv_obj = dv_qs.first()
            if not dv_obj:
                return HttpResponseBadRequest("الزيارة اليومية المختارة غير متاحة.")
            if mgr and obj.rep_id and dv_obj.rep_id != obj.rep_id:
                return HttpResponseBadRequest("الزيارة لا تخص هذا المندوب.")
        else:
            if dv_id and str(dv_id).isdigit():
                dv_qs = DailyVisit.objects.filter(id=int(dv_id), is_deleted=False, client__isnull=True)
                if not mgr:
                    dv_qs = dv_qs.filter(rep=request.user)
                dv_obj = dv_qs.first()
                if dv_obj and mgr and obj.rep_id and dv_obj.rep_id != obj.rep_id:
                    return HttpResponseBadRequest("الزيارة لا تخص هذا المندوب.")

        # حقول العميل (يدوي بالكامل)
        obj.doctor_name = (data.get('doctor_name') or '').strip()
        obj.entity_name = (data.get('entity_name') or '').strip()
        obj.city        = (data.get('city') or '').strip()
        obj.location    = (data.get('location') or '').strip()
        obj.phone       = (data.get('phone') or '').strip()
        obj.email       = (data.get('email') or '').strip()
        obj.status      = (data.get('status') or '').strip()
        obj.notes       = (data.get('notes') or '').strip()

        # week_number: لو مش مبعوت، ناخده من الزيارة (علشان الأرشيف)
        wknum = (data.get('week_number') or '').strip()
        if wknum.isdigit():
            obj.week_number = int(wknum)
        elif dv_obj and getattr(dv_obj, 'week_number', None):
            obj.week_number = dv_obj.week_number
        if not obj.week_number:
            return HttpResponseBadRequest("Week number مفقود (حدده أو اختار زيارة لها أسبوع).")

        # حفظ + أرشفة فورية (عميل + زيارة) داخل Transaction
        with transaction.atomic():
            obj.save()

            # اربط الزيارة المختارة (لو موجودة)
            if dv_obj:
                dv_obj.client = obj
                dv_obj.save(update_fields=['client'])

            # أنشئ/حدّث ArchiveWeekly لهذا الأسبوع (لو ما اتعملش وقت الـApprove)
            aw, created_aw = ArchiveWeekly.objects.get_or_create(
                rep=obj.rep, week_no=obj.week_number,
                defaults={
                    'planned_date'   : getattr(getattr(dv_obj, 'weekly_plan', None), 'planned_date', None) if dv_obj else None,
                    'aa_plan'        : getattr(getattr(dv_obj, 'weekly_plan', None), 'aa_plan', '') if dv_obj else '',
                    'targeted_line'  : getattr(getattr(dv_obj, 'weekly_plan', None), 'product_line', '') if dv_obj else '',
                    'entity_type'    : getattr(getattr(dv_obj, 'weekly_plan', None), 'entity_type', '') if dv_obj else '',
                    'specialization' : getattr(getattr(dv_obj, 'weekly_plan', None), 'specialization', '') if dv_obj else '',
                    'visit_objective': getattr(getattr(dv_obj, 'weekly_plan', None), 'visit_objective', '') if dv_obj else '',
                    'entity_address' : getattr(getattr(dv_obj, 'weekly_plan', None), 'entity_address', '') if dv_obj else '',
                    'notes'          : getattr(getattr(dv_obj, 'weekly_plan', None), 'notes', '') if dv_obj else '',
                    'status'         : 'Approved',  # اتعمل Approve قبل كده
                    'total_visits'   : 0,
                    'unique_clients' : 0,
                }
            )

            # عدّل التعدادات (نزيد زيارة + عميل)
            try:
                aw.total_visits = (aw.total_visits or 0) + 1
                aw.unique_clients = (aw.unique_clients or 0) + 1
                # تقدر تكمل أي تحديثات إضافية حسب نموذجك
                aw.save()
            except Exception:
                pass

            # Soft-delete للزيارة والعميل فورًا (يختفوا من النظام)
            now = timezone.now()
            if dv_obj and hasattr(dv_obj, 'is_deleted'):
                dv_obj.is_deleted = True
                dv_obj.deleted_at = now
                try:
                    dv_obj.deleted_by = obj.rep
                except Exception:
                    pass
                dv_obj.save(update_fields=['is_deleted', 'deleted_at'] + (['deleted_by'] if hasattr(dv_obj, 'deleted_by') else []))

            if hasattr(obj, 'is_deleted'):
                obj.is_deleted = True
                obj.deleted_at = now
                try:
                    obj.deleted_by = obj.rep
                except Exception:
                    pass
                obj.save(update_fields=['is_deleted', 'deleted_at'] + (['deleted_by'] if hasattr(obj, 'deleted_by') else []))

        messages.success(request, f"تم الحفظ والأرشفة الفورية لأسبوع W{obj.week_number}. البيانات دلوقتي في الأرشيف (و/أو الـAccounts).")
        return redirect('clients:list')

    # ---------------------- Table annotations ----------------------
    qs = qs.annotate(
        daily_visits_count=Count('dailyvisits', filter=Q(dailyvisits__is_deleted=False)),
        last_visit_date=Max('dailyvisits__visit_date', filter=Q(dailyvisits__is_deleted=False)),
    )

    # Rep choices
    rep_choices = (
        User.objects.filter(groups__name='Rep', is_active=True).order_by('first_name', 'username')
        if mgr else User.objects.filter(id=request.user.id)
    )

    return render(request, 'clients/clients.html', {
        'clients': qs,
        'rep_choices': rep_choices,
        'show': show,
        'q': q,
        'week': wk,
        'hide_archived': '1' if hide_archived else '0',
        'daily_visits': dv_dropdown,
    })
