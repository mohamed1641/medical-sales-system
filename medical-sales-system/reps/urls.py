from django.urls import path
from . import views

app_name = 'reps'
urlpatterns = [
    path('', views.reps_list, name='list'),
    path('<int:pk>/activate/', views.activate_rep, name='activate'),
    path('<int:pk>/deactivate/', views.deactivate_rep, name='deactivate'),
    path('<int:pk>/delete/', views.delete_rep, name='delete'),
    path('create/', views.create_rep, name='create'),

]
