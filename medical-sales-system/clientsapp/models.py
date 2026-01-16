# clientsapp/models.py
from django.db import models
from django.contrib.auth.models import User

class Client(models.Model):
    doctor_name  = models.CharField(max_length=255)
    entity_name  = models.CharField(max_length=255, blank=True)
    city         = models.CharField(max_length=120, blank=True)
    location     = models.CharField(max_length=255, blank=True)
    phone        = models.CharField(max_length=40, blank=True)
    email        = models.EmailField(blank=True)
    status       = models.CharField(max_length=40, blank=True)  # Potential/Active/Not Interested
    notes        = models.TextField(blank=True)
    rep          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='clients')

    # رقم الأسبوع
    week_number  = models.PositiveSmallIntegerField(null=True, blank=True)

    # أرشفة
    is_deleted   = models.BooleanField(default=False)
    deleted_at   = models.DateTimeField(null=True, blank=True)
    deleted_by   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='deleted_clients')

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.doctor_name or self.entity_name

    class Meta:
        indexes = [
            models.Index(fields=['rep']),
            models.Index(fields=['week_number']),
            models.Index(fields=['is_deleted']),
        ]
