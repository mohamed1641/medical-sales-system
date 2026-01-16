from django.contrib import admin
from .models import ArchiveWeekly

@admin.register(ArchiveWeekly)
class ArchiveWeeklyAdmin(admin.ModelAdmin):
    """
    Admin آمن مع اختلاف أسماء الحقول:
    - بنعرض Entity/City/Status كـ methods (علشان لو الحقول مش موجودة مايحصلش Error).
    - الفلاتر على حقول مؤكدة بس: week_no, planned_date, rep.
    - search_fields آمنة على الـ Rep.
    """
    list_display  = (
        'id',
        'archived_at',
        'planned_date',
        'week_no',
        'rep',
        'get_entity',    # بدل entity
        'get_city',      # بدل city
        'get_status',    # بدل status المباشر لو مش موجود
        'total_visits',
        'unique_clients',
    )
    list_filter   = ('week_no', 'planned_date', 'rep')  # شِلنا city/status عشان ما نكسرش الـ admin
    search_fields = ('rep__username', 'rep__first_name', 'rep__last_name')
    readonly_fields = ('archived_at', 'total_visits', 'unique_clients')

    # ===== أعمدة محسوبة آمنة =====
    def get_entity(self, obj):
        # جرّب أشهر أسماء الحقول الممكنة، وإلا سيّبها فاضية
        return (
            getattr(obj, 'entity', None)
            or getattr(obj, 'entity_name', None)
            or getattr(obj, 'account', None)
            or ''
        )
    get_entity.short_description = 'Entity'

    def get_city(self, obj):
        return (
            getattr(obj, 'city', None)
            or getattr(obj, 'client_city', None)
            or getattr(obj, 'account_city', None)
            or ''
        )
    get_city.short_description = 'City'

    def get_status(self, obj):
        return getattr(obj, 'status', '')  # لو مش موجودة هتطلع فاضية
    get_status.short_description = 'Status'
