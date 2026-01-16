# accounts/views.py
# --- ADD THESE IMPORTS (top of accounts/views.py) ---
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q
from django.apps import apps
import csv

# لو عامل موديل البروفايل في reps/models.py
from reps.models import RepProfile


# -------- Helpers --------
def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()


# -------- Auth Flow --------
@login_required
def post_login_redirect(request):
    """
    بعد تسجيل الدخول:
    - Manager → dashboard:main
    - غير كده (Rep) → plans:weekly
    """
    if request.user.groups.filter(name='Manager').exists():
        return redirect('dashboard:main')
    return redirect('plans:weekly')


# -------- Accounts (Manager-only Read-Only) --------
@login_required
@user_passes_test(is_manager)
def account_overview(request):
    """
    Manager-only overview:
    - يعرض المؤرشف افتراضيًا (show=deleted) عشان تبان الداتا اللي خلصت وتحوّلت للأرشيف/الأكونتس
    - فلتر week + بحث q
    - Export CSV لنفس الفلاتر
    بارامترات GET:
      - show: deleted | active | all   (default: deleted)
      - week: رقم الأسبوع
      - q: نص البحث
      - source: visits | clients       (للـ CSV وأيضًا ممكن تستخدمه في الواجهة)
      - export: csv                    (لو عايز تصدّر)
    """
    DailyVisit = apps.get_model('visits', 'DailyVisit')
    Client     = apps.get_model('clientsapp', 'Client')

    show  = (request.GET.get('show') or 'deleted').strip().lower()
    week  = (request.GET.get('week') or '').strip()
    q     = (request.GET.get('q') or '').strip()
    src   = (request.GET.get('source') or 'visits').strip().lower()
    do_csv = (request.GET.get('export') or '').strip().lower() == 'csv'

    # أساس الـ QuerySets (بدون limit علشان الفلاتر والتصدير)
    visits_qs  = DailyVisit.objects.select_related('rep', 'client').order_by('-visit_date', '-id') if DailyVisit else []
    clients_qs = Client.objects.select_related('rep').order_by('-created_at', '-id')                if Client     else []

    # فلتر المؤرشف/النشط/الكل
    def apply_show(qs):
        if not hasattr(qs, 'filter'):
            return qs
        if show == 'deleted':
            return qs.filter(is_deleted=True)
        elif show == 'active':
            return qs.filter(is_deleted=False)
        return qs

    visits_qs  = apply_show(visits_qs)
    clients_qs = apply_show(clients_qs)

    # فلتر الأسبوع
    if week.isdigit():
        wk = int(week)
        if hasattr(DailyVisit, 'week_number'):
            visits_qs = visits_qs.filter(week_number=wk)
        if hasattr(Client, 'week_number'):
            clients_qs = clients_qs.filter(week_number=wk)

    # بحث نصي بسيط
    if q:
        if hasattr(DailyVisit, 'objects'):
            visits_qs = visits_qs.filter(
                Q(entity__icontains=q) |
                Q(doctor_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(city__icontains=q) |
                Q(visit_objective__icontains=q) |
                Q(other_objective__icontains=q)
            )
        if hasattr(Client, 'objects'):
            clients_qs = clients_qs.filter(
                Q(doctor_name__icontains=q) |
                Q(entity_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(city__icontains=q) |
                Q(status__icontains=q)
            )

    # ===== Export CSV (بنفس الفلاتر) =====
    if do_csv:
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{src}.csv"'
        w = csv.writer(resp)

        if src == 'clients':
            w.writerow(['ID','Week','Doctor Name','Entity Name','Phone','Email','City','Location',
                        'Status','Notes','Rep','Created','Updated'])
            for c in clients_qs:
                w.writerow([
                    getattr(c, 'id', ''),
                    getattr(c, 'week_number', ''),
                    getattr(c, 'doctor_name', ''),
                    getattr(c, 'entity_name', ''),
                    getattr(c, 'phone', ''),
                    getattr(c, 'email', ''),
                    getattr(c, 'city', ''),
                    getattr(c, 'location', ''),
                    getattr(c, 'status', ''),
                    getattr(c, 'notes', ''),
                    getattr(getattr(c, 'rep', None), 'username', ''),
                    getattr(c, 'created_at', ''),
                    getattr(c, 'updated_at', ''),
                ])
            return resp

        # visits (default)
        w.writerow(['ID','Week','Visit Date','Actual DateTime','Entity','Address','City','Phone',
                    'Visit Objective','Other Objective','Client (Entity)','Rep',
                    'Created','Updated'])
        for v in visits_qs:
            w.writerow([
                getattr(v, 'id', ''),
                getattr(v, 'week_number', ''),
                getattr(v, 'visit_date', ''),
                getattr(v, 'actual_datetime', ''),
                getattr(v, 'entity', ''),
                getattr(v, 'address', ''),
                getattr(v, 'city', ''),
                (getattr(v, 'phone', '') or getattr(v, 'phone_number', '')),
                (getattr(v, 'visit_outcome', '') or getattr(v, 'visit_objective', '')),
                getattr(getattr(v, 'client', None), 'entity_name', ''),
                getattr(getattr(v, 'rep', None), 'username', ''),
                getattr(v, 'created_at', ''),
                getattr(v, 'updated_at', ''),
            ])
        return resp

    # للعرض فقط: حدّ أقصى 2000 صف عشان الأداء في الصفحة
    visits_show  = visits_qs[:2000]  if hasattr(visits_qs, 'all')  else []
    clients_show = clients_qs[:2000] if hasattr(clients_qs, 'all') else []

    return render(request, 'accounts/account.html', {
        'show': show,
        'week': week,
        'q': q,
        'visits': visits_show,
        'clients': clients_show,
    })


# -------- Create User (Manager-only) --------
@login_required
@user_passes_test(is_manager)
def create_user_view(request):
    """
    Manager-only: إنشاء مستخدم (Rep/Manager).
    يستقبل كمان phone1/phone2/territory ويخزنهم في RepProfile.
    """
    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        role       = request.POST.get('role', 'Rep')
        active     = bool(request.POST.get('active'))

        # الحقول الجديدة للبروفايل
        phone1    = request.POST.get('phone1', '').strip()
        phone2    = request.POST.get('phone2', '').strip()
        territory = request.POST.get('territory', '').strip()

        # فحوصات سريعة
        if not username or not password1:
            messages.error(request, 'Username و Password مطلوبين.')
            return redirect('accounts:create')

        if password1 != password2:
            messages.error(request, 'Passwords غير متطابقة.')
            return redirect('accounts:create')

        try:
            user = User.objects.create_user(
                username=username, password=password1, email=email,
                first_name=first_name, last_name=last_name
            )
        except IntegrityError:
            messages.error(request, 'Username موجود بالفعل.')
            return redirect('accounts:create')

        user.is_active = active
        user.save()

        # ضم للمجموعة
        group_name = 'Manager' if role == 'Manager' else 'Rep'
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)

        # إنشاء/تحديث بروفايل الرپ بالحقول الجديدة
        RepProfile.objects.update_or_create(
            user=user,
            defaults={
                'phone1': phone1,
                'phone2': phone2,
                'territory': territory
            }
        )

        messages.success(request, f'تم إنشاء المستخدم {username} كـ {group_name}.')
        # بعد الإنشاء: ارجع لقائمة الـReps (reps:list)
        return redirect('reps:list')

    # GET: جرّب نرندر التمبلت؛ لو مش موجود، اعرض Placeholder بسيط
    try:
        return render(request, 'accounts/create.html')
    except Exception:
        return HttpResponse(
            "<h3>Create User (Temporary)</h3>"
            "<p>جهّز التمبلت: <code>templates/accounts/create.html</code></p>",
            content_type="text/html"
        )
