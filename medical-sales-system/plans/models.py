# plans/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User


class WeeklyPlan(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    aa_plan         = models.CharField(max_length=200)
    planned_date    = models.DateField()
    product_line    = models.CharField(max_length=50)
    entity_address  = models.CharField(max_length=255)
    entity_type     = models.CharField(max_length=50)
    specialization  = models.CharField(max_length=100)
    notes           = models.CharField(max_length=255, blank=True)
    visit_objective = models.CharField(max_length=100)
    other_objective = models.CharField(max_length=255, blank=True)

    rep             = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='weekly_plans'
    )

    week_number     = models.PositiveSmallIntegerField()
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    # أرشفة
    is_deleted      = models.BooleanField(default=False)
    deleted_at      = models.DateTimeField(null=True, blank=True)
    deleted_by      = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='deleted_weekly_plans'
    )

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # -------- Helpers / Compat --------
    def __str__(self):
        wk = self.week_number or '—'
        rep = self.rep.get_full_name() or self.rep.username if self.rep_id else '—'
        return f"W{wk} • {self.planned_date} • {rep}"

    @property
    def week_no(self):
        """Compat alias لو في كود قديم بينادي week_no"""
        return self.week_number

    def clean(self):
        if self.week_number and not (1 <= int(self.week_number) <= 53):
            raise ValidationError({"week_number": "Week number must be between 1 and 53."})

    def soft_delete(self, by: User | None = None):
        """أرشفة ناعمة بدل الحذف"""
        self.is_deleted = True
        self.deleted_by = by if by else self.deleted_by
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_by', 'deleted_at'])

    class Meta:
        ordering = ['-planned_date', '-id']
        indexes = [
            models.Index(fields=['planned_date']),
            models.Index(fields=['rep']),
            models.Index(fields=['week_number']),
            models.Index(fields=['status']),
            models.Index(fields=['is_deleted']),
        ]
