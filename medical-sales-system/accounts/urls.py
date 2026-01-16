from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

# مهم عشان الnamespace يشتغل كويس مع include(namespace='accounts')
app_name = 'accounts'

urlpatterns = [
    # Login (صفحة اللوجين بتاعتك في templates/accounts/login.html)
    path('login/', LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True  # لو مسجّل دخول، يروح لِما بعد اللوجين
    ), name='login'),

    # Logout (هيحوّل بناءً على LOGOUT_REDIRECT_URL في settings)
    path('logout/', LogoutView.as_view(), name='logout'),

    # بعد اللوجين نحدد الاتجاه حسب الجروب
    path('post-login/', views.post_login_redirect, name='post_login'),

    # صفحة العرض فقط (Manager-only) — اتأكد إن @user_passes_test موجودة في views
    path('account/', views.account_overview, name='account'),

    # إنشاء مستخدم (Manager-only) — create_user_view موجودة في views
    path('create/', views.create_user_view, name='create'),
]
