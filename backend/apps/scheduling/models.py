from django.db import models
from django.db.models import Q

from apps.common import Timestamped


class SessionKind(models.TextChoices):
    FIXED = "fixed"
    OUTREACH = "outreach"


class SessionStatus(models.TextChoices):
    PLANNED = "planned"
    HELD = "held"


class OutreachSession(Timestamped):
    source_ref = models.CharField(max_length=16, unique=True, null=True, blank=True)
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="sessions")
    date = models.DateField()
    kind = models.CharField(max_length=8, choices=SessionKind.choices)
    location_name = models.CharField(max_length=120)
    capacity = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=SessionStatus.choices, default=SessionStatus.PLANNED)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=SessionKind.values), name="session_kind_valid"),
            models.CheckConstraint(condition=Q(status__in=SessionStatus.values), name="session_status_valid"),
        ]


class SessionPlanItem(Timestamped):
    session = models.ForeignKey(OutreachSession, on_delete=models.CASCADE, related_name="plan_items")
    child = models.ForeignKey("passport.Child", on_delete=models.PROTECT, related_name="+")
    schedule_dose = models.ForeignKey("passport.ScheduleDose", on_delete=models.PROTECT, related_name="+")
    priority_rank = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "child", "schedule_dose"], name="planitem_one_per_session_child_dose"
            )
        ]


class SessionAttendance(Timestamped):
    session = models.ForeignKey(OutreachSession, on_delete=models.CASCADE, related_name="attendance")
    child = models.ForeignKey("passport.Child", on_delete=models.PROTECT, related_name="+")
    attended = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "child"], name="attendance_one_per_session_child")
        ]
