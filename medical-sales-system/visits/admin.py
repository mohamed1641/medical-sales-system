# visits/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import DailyVisit

@admin.action(description="Soft delete (أرشفة)")
def soft_delete(modeladmin, request, queryset):
    queryset.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)

@admin.action(description="Restore (استرجاع)")
def restore(modeladmin, request, queryset):
    queryset.update(is_deleted=False, deleted_at=None, deleted_by=None)

@admin.register(DailyVisit)
class DailyVisitAdmin(admin.ModelAdmin):
    list_display  = ('id','visit_date','time_shift','visit_status','visit_objective',
                     'entity','city','phone','rep','week_number','weekly_plan')
    list_filter   = ('visit_date','visit_status','rep','city','week_number')
    search_fields = ('entity','address','city','phone','client_doctor',
                     'rep__username','rep__first_name','rep__last_name')
    autocomplete_fields = ('rep','client','weekly_plan')
    readonly_fields = ('created_at','updated_at')
    actions = (soft_delete, restore)
