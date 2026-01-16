# visits/models.py
from django.db import models
from django.contrib.auth.models import User


class DailyVisit(models.Model):
    client          = models.ForeignKey(
        'clientsapp.Client',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dailyvisits'
    )

    actual_datetime = models.DateTimeField(null=True, blank=True)
    visit_date      = models.DateField()

    time_shift      = models.CharField(max_length=10, blank=True)
    visit_status    = models.CharField(max_length=20, blank=True)

    weekly_plan     = models.ForeignKey(
        'plans.WeeklyPlan',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='daily_visits'
    )

    client_doctor   = models.CharField(max_length=255, blank=True)

    entity          = models.CharField(max_length=200)
    address         = models.CharField(max_length=255, blank=True)
    city            = models.CharField(max_length=100, blank=True)
    phone           = models.CharField(max_length=30,  blank=True)

    visit_objective = models.CharField(max_length=100, blank=True)
    other_objective = models.CharField(max_length=255, blank=True)

    # رقم الأسبوع لترحيل التسك
    week_number     = models.PositiveSmallIntegerField(null=True, blank=True)

    rep             = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='daily_visits'
    )

    # أرشفة
    is_deleted      = models.BooleanField(default=False)
    deleted_at      = models.DateTimeField(null=True, blank=True)
    deleted_by      = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='deleted_daily_visits'
    )

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-visit_date', '-id']
        indexes = [
            models.Index(fields=['visit_date']),
            models.Index(fields=['rep']),
            models.Index(fields=['client']),
            models.Index(fields=['weekly_plan']),
            models.Index(fields=['week_number']),
            models.Index(fields=['is_deleted']),
        ]

    def save(self, *args, **kwargs):
        # 1) لو التاريخ الفعلي موجود ومفيش visit_date، خده منه
        if not self.visit_date and self.actual_datetime:
            try:
                self.visit_date = self.actual_datetime.date()
            except Exception:
                pass

        # 2) استنتاج رقم الأسبوع من البلان (يدعم week_number أو week_no)
        if not self.week_number and self.weekly_plan_id:
            wp = self.weekly_plan
            wk = getattr(wp, 'week_number', None)
            if wk is None:
                wk = getattr(wp, 'week_no', None)
            if wk:
                self.week_number = wk

        # 3) لو مربوط بعميل و في حقول ناقصة، كمّلها من العميل
        c = getattr(self, 'client', None)
        if c:
            if not self.entity:
                self.entity = getattr(c, 'entity_name', '') or self.entity
            if not self.address:
                self.address = getattr(c, 'location', '') or self.address
            if not self.city:
                self.city = getattr(c, 'city', '') or self.city
            if not self.phone:
                self.phone = getattr(c, 'phone', '') or self.phone
            if not self.client_doctor:
                self.client_doctor = getattr(c, 'doctor_name', '') or self.client_doctor

        super().save(*args, **kwargs)

    def __str__(self):
        dt = self.visit_date or (self.actual_datetime.date() if self.actual_datetime else '')
        who = self.entity or (self.client.entity_name if self.client_id else '')
        return f"{dt} — {who}".strip()
