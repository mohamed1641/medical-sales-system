# plans/urls.py
from django.urls import path
from . import views, api

app_name = 'plans'

urlpatterns = [
    path('', views.weekly_view, name='weekly'),

    # NOTE: شلنا move-to-daily لأنه غير مستخدم ومفيش دالة ليه
    path('weekly/<int:pk>/approve/', views.approve_weekly, name='approve'),
    path('weekly/<int:pk>/reject/',  views.reject_weekly,  name='reject'),

    path('api/weeks/', api.api_weeks, name='api_weeks'),
    path('api/by-week/', api.api_plans_by_week, name='api_plans_by_week'),
    path('api/list/', api.api_list, name='api_list'),
    path('api/archive/<int:pk>/', api.api_archive, name='api_archive'),
]
