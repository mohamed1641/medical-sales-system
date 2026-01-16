# visits/urls.py
from django.urls import path
from . import views
from . import api

app_name = "visits"

urlpatterns = [
    path('', views.daily_view, name='daily'),
    # ❌ اتشال sync تمامًا
    path('<int:pk>/start/', views.start_from_weekly, name='start_from_weekly'),
    path('<int:pk>/move-to-client/', views.move_to_client, name='move_to_client'),

    # APIs (زي ما هي)
    path('api/list/', api.api_list, name='api_list'),
    path('api/save/', api.api_save, name='api_save'),
    path('api/archive/<int:pk>/', api.api_archive, name='api_archive'),
    path('api/delete/<int:pk>/', api.api_delete, name='api_delete'),
]

