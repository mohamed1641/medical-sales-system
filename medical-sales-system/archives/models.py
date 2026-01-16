# archives/models.py
from django.db import models
from django.contrib.auth.models import User

class ArchiveWeekly(models.Model):
    archived_at      = models.DateTimeField(auto_now_add=True)

    # مرن وتوافق مع الداتا القديمة
    planned_date     = models.DateField(null=True, blank=True)
    week_no          = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)

    rep              = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='archived_weekly_rows'
    )

    aa_plan          = models.CharField(max_length=50,  blank=True)
    targeted_line    = models.CharField(max_length=100, blank=True)
    entity_type      = models.CharField(max_length=100, blank=True)
    specialization   = models.CharField(max_length=200, blank=True)
    visit_objective  = models.CharField(max_length=200, blank=True)

    # الاسم النهائي المتسق مع WeeklyPlan
    entity_address   = models.CharField(max_length=255, blank=True)

    notes            = models.TextField(blank=True)
    status           = models.CharField(max_length=50,  blank=True)

    # NEW: سنابشوت أرقام للأسبوع (بيتم تحديثهم أوتوماتك من الـ API)
    total_visits     = models.PositiveIntegerField(default=0)
    unique_clients   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-archived_at', '-planned_date', '-id']
        indexes = [
            models.Index(fields=['week_no']),
            models.Index(fields=['planned_date']),
            models.Index(fields=['rep']),
        ]
        # لو عايز تمنع تكرار سنابشوتات كتير لنفس الأسبوع ونفس الـrep، فكّ الكومنت اللي تحت:
        # unique_together = (('week_no', 'rep', 'planned_date'),)

    def __str__(self):
        repname = getattr(self.rep, 'username', '—')
        wlabel = self.week_number or '—'
        return f"Week {wlabel} — {self.planned_date or '—'} — {repname}"

    # Alias علشان تتعامل بـ week_number في القوالب/الـviews
    @property
    def week_number(self):
        return self.week_no
