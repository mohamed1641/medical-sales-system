from django.urls import path
from . import views

app_name = 'archives'
urlpatterns = [
    path('', views.archives_list, name='list'),
    path('sync/', views.sync_archives, name='sync'), 
]
