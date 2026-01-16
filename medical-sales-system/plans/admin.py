# plans/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import WeeklyPlan

@admin.action(description="Soft delete (أرشفة)")
def soft_delete(modeladmin, request, queryset):
    queryset.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user)

@admin.action(description="Restore (استرجاع)")
def restore(modeladmin, request, queryset):
    queryset.update(is_deleted=False, deleted_at=None, deleted_by=None)

@admin.register(WeeklyPlan)
class WeeklyPlanAdmin(admin.ModelAdmin):
    list_display = ('id','planned_date','week_number','rep','status','aa_plan','visit_objective','product_line','entity_type')
    list_filter  = ('status','planned_date','week_number','rep','product_line','entity_type')
    search_fields = ('aa_plan','visit_objective','other_objective','entity_address','specialization','notes',
                     'rep__username','rep__first_name','rep__last_name')
    autocomplete_fields = ('rep',)
    readonly_fields = ('created_at','updated_at')
    actions = (soft_delete, restore)
