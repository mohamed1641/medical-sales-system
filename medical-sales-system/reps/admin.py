from django.contrib import admin
from .models import RepProfile

@admin.register(RepProfile)
class RepProfileAdmin(admin.ModelAdmin):
    list_display = ('user','phone1','phone2','territory')
    search_fields = ('user__username','user__first_name','user__last_name','phone1','phone2','territory')
