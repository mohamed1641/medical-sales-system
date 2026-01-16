# clientsapp/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import Client

@admin.action(description="Soft delete (أرشفة)")
def soft_delete(modeladmin, request, queryset):
    queryset.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)

@admin.action(description="Restore (استرجاع)")
def restore(modeladmin, request, queryset):
    queryset.update(is_deleted=False, deleted_at=None, deleted_by=None)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ('id','doctor_name','entity_name','city','status','rep','week_number','is_deleted','created_at')
    list_filter   = ('status','city','rep','week_number','is_deleted','created_at')
    search_fields = ('doctor_name','entity_name','city','location','phone','email','notes',
                     'rep__username','rep__first_name','rep__last_name')
    autocomplete_fields = ('rep',)
    readonly_fields = ('created_at','updated_at')
    actions = (soft_delete, restore)
