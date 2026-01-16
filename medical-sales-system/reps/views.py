from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.http import HttpResponse
from .models import RepProfile # لو لسه عامل الموديل

def is_manager(u):
    return u.is_authenticated and u.groups.filter(name='Manager').exists()

@login_required
@user_passes_test(is_manager)  # أو @user_passes_test(is_manager, login_url='accounts:login')

def reps_list(request):
    q    = (request.GET.get('q') or '').strip()
    role = (request.GET.get('role') or '').strip()

    size = int(request.GET.get('page_size') or request.GET.get('size') or 10)
    page = int(request.GET.get('page') or 1)

    # نجيب Rep و Manager مع بعض
    qs = (User.objects
          .filter(groups__name__in=['Rep', 'Manager'])
          .distinct()
          .select_related('repprofile')   # بروفايل للـ Rep
          .prefetch_related('groups')     # علشان نقرأ اسم الجروب من غير Queries زيادة
          .order_by('first_name', 'username'))

    # بحث عام
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(email__icontains=q)      |
            Q(username__icontains=q)   |
            Q(repprofile__phone1__icontains=q) |
            Q(repprofile__phone2__icontains=q) |
            Q(repprofile__territory__icontains=q)
        )

    # فلتر Role (جديد)
    if role in ('Rep', 'Manager'):
        qs = qs.filter(groups__name=role)

    # Export CSV (مضاف عمود Role)
    if request.GET.get('export') == 'csv':
        import csv
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="reps.csv"'
        w = csv.writer(resp)
        w.writerow(['#','First Name','Last Name','Email','Phone 1','Phone 2','Territory','Role','Active'])
        for idx, u in enumerate(qs, start=1):
            groups = [g.name for g in u.groups.all()]
            role_label = 'Manager' if 'Manager' in groups else 'Rep'   # rename علشان ما نغطيش على متغير GET
            p = getattr(u, 'repprofile', None)
            w.writerow([
                idx, u.first_name, u.last_name, u.email,
                (p.phone1 if p else ''), (p.phone2 if p else ''), (p.territory if p else ''),
                role_label,
                ('Active' if u.is_active else 'Inactive')
            ])
        return resp

    # Pagination
    total = qs.count()
    start = (page - 1) * size
    reps  = qs[start:start+size]
    page_total = (total + size - 1) // size

    return render(request, 'reps/reps.html', {
        'reps': reps,
        'q': q,
        'role': role,                 # NEW: لو محتاجه في التمبلت
        'size': size,
        'page': page,
        'page_total': page_total,
        'total': total,
    })

@login_required
@user_passes_test(is_manager)  # التأكد أن المستخدم هو مدير
def activate_rep(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # التأكد أن المستخدم ليس هو نفسه (المدير) وأيضًا التأكد من أنه ليس نشطًا
        if user != request.user:  # المدير لا يمكنه تفعيل حسابه الشخصي
            user.is_active = True
            user.save()
            messages.success(request, f'{user.username} تم تفعيل الحساب بنجاح.')
        else:
            messages.error(request, 'لا يمكنك تفعيل حسابك الشخصي.')
    return redirect('reps:list')


@login_required
@user_passes_test(is_manager)  # التأكد أن المدير فقط يمكنه إلغاء التفعيل
def deactivate_rep(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # التأكد أن المستخدم ليس نفسه (المدير) وأيضا التأكد أن المستخدم هو Rep
        if user != request.user:
            user.is_active = False
            user.save()
            messages.warning(request, f'{user.username} تم إلغاء تفعيل حسابه.')
        else:
            messages.error(request, 'لا يمكنك إلغاء تفعيل حسابك الشخصي.')
    return redirect('reps:list')

@login_required
@user_passes_test(is_manager)
def delete_rep(request, pk):
    """
    Manager-only: حذف حساب Rep أو مدير (لكن لا يمكن حذف المديرين الآخرين أو المستخدمين الأساسيين)
    """
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # تأكد من أنه ليس مديرًا آخر
        if user.is_superuser or user == request.user:
            messages.error(request, 'Cannot delete this user.')
            return redirect('reps:list')
        if user.groups.filter(name='Manager').exists():
            messages.error(request, 'Cannot delete another manager.')
            return redirect('reps:list')
        username = user.username
        user.delete()
        messages.success(request, f'{username} deleted.')
    return redirect('reps:list')

    
def create_rep(request):
    if request.method == 'POST':
        # جمع البيانات من النموذج
        username = request.POST.get('username').strip()
        first_name = request.POST.get('first_name').strip()
        last_name = request.POST.get('last_name').strip()
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()
        phone1 = request.POST.get('phone1').strip()
        phone2 = request.POST.get('phone2').strip()
        territory = request.POST.get('territory').strip()

        # التحقق من وجود الحقول المطلوبة
        if not username or not password:
            messages.error(request, 'Please fill required fields correctly.')
            return render(request, 'reps/create_rep.html')

        # إنشاء المستخدم الجديد
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name, is_active=True
        )
        
        # إنشاء RepProfile للـ Rep
        RepProfile.objects.create(
            user=user,
            phone1=phone1,
            phone2=phone2,
            territory=territory
        )

        # عرض رسالة نجاح
        messages.success(request, f'User {username} created as Rep.')
        return redirect('reps:list')

    return render(request, 'reps/reps.html')