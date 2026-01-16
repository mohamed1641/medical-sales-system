from django.db import models
from django.contrib.auth.models import User

class RepProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='repprofile')
    phone1 = models.CharField(max_length=20, blank=True)
    phone2 = models.CharField(max_length=20, blank=True)
    territory = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_username()
