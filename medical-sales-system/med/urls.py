"""
URL configuration for med project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # root → /users/login/
    path('', RedirectView.as_view(pattern_name='accounts:login', permanent=False)),

    path('admin/', admin.site.urls),

    # accounts app URLs تحت prefix واحد /users/
    path('users/', include(('accounts.urls', 'accounts'), namespace='accounts')),

    # بدائل لطُرق /accounts/... كـ Redirects للأسماء (اختياري)
    path('accounts/account/',  RedirectView.as_view(pattern_name='accounts:account',  permanent=False)),
    path('accounts/create/',   RedirectView.as_view(pattern_name='accounts:create',   permanent=False)),
    path('accounts/login/',    RedirectView.as_view(pattern_name='accounts:login',    permanent=False)),
    path('accounts/logout/',   RedirectView.as_view(pattern_name='accounts:logout',   permanent=False)),
    path('accounts/post-login/', RedirectView.as_view(pattern_name='accounts:post_login', permanent=False)),

    # باقي التطبيقات
    path('plans/',     include(('plans.urls', 'plans'), namespace='plans')),
    path('visits/',    include(('visits.urls', 'visits'), namespace='visits')),
    path('clients/',   include(('clientsapp.urls', 'clients'), namespace='clients')),
    path('reps/',      include(('reps.urls', 'reps'), namespace='reps')),
    path('archives/',  include(('archives.urls', 'archives'), namespace='archives')),
    path('dashboard/', include(('dashboardapp.urls', 'dashboard'), namespace='dashboard')),

]
