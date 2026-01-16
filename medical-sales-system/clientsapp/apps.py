# clientsapp/apps.py
from django.apps import AppConfig

class ClientsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clientsapp'

    def ready(self):
        from . import signals  # noqa: F401
