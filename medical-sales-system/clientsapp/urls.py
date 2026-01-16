# clientsapp/urls.py
from django.urls import path
from . import views, api

app_name = 'clients'  # مهم علشان {% url 'clients:list' %}

urlpatterns = [
    path('', views.clients_list, name='list'),                # صفحة العملاء
    path('api/list/', api.api_list, name='api_list'),         # API
    path('api/archive/<int:pk>/', api.api_archive, name='api_archive'),
    path('api/finalize/', api.api_finalize, name='api_finalize'),
]
