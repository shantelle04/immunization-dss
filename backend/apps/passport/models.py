import uuid

from django.db import models
from django.db.models import F, Q

from apps.common import Timestamped


class Antigen(Timestamped):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=80)
    doses_per_vial = models.SmallIntegerField()
    open_vial_policy = models.BooleanField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(doses_per_vial__gte=1), name="antigen_doses_per_vial_positive")
        ]

    def __str__(self) -> str:
        return self.code


class ScheduleDose(Timestamped):
    dose_code = models.CharField(max_length=12, unique=True)
    antigen = models.ForeignKey(Antigen, on_delete=models.PROTECT, related_name="doses")
    dose_number = models.SmallIntegerField()
    contact = models.CharField(max_length=8)
    recommended_age_days = models.IntegerField()
    min_age_days = models.IntegerField()
    max_age_days = models.IntegerField()
    min_interval_days = models.IntegerField()

    class Meta:
        ordering = ["recommended_age_days", "dose_code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(min_age_days__lte=F("recommended_age_days"))
                & Q(recommended_age_days__lte=F("max_age_days")),
                name="scheduledose_age_window_ordered",
            )
        ]

    def __str__(self) -> str:
        return self.dose_code


class Sex(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"


class Child(Timestamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    system_id = models.CharField(max_length=32, unique=True)
    source_ref = models.CharField(max_length=16, unique=True, null=True, blank=True)
    given_name = models.CharField(max_length=80)
    family_name = models.CharField(max_length=80)
    sex = models.CharField(max_length=1, choices=Sex.choices)
    date_of_birth = models.DateField()
    caregiver_name = models.CharField(max_length=120)
    registration_facility = models.ForeignKey(
        "facilities.Facility", on_delete=models.PROTECT, related_name="registered_children"
    )
    registered_on = models.DateField()
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["family_name", "date_of_birth"], name="child_name_dob_idx")]
        constraints = [models.CheckConstraint(condition=Q(sex__in=Sex.values), name="child_sex_valid")]

    def __str__(self) -> str:
        return self.system_id


class ImmunizationEvent(Timestamped):
    source_ref = models.CharField(max_length=16, unique=True, null=True, blank=True)
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name="events")
    schedule_dose = models.ForeignKey(ScheduleDose, on_delete=models.PROTECT, related_name="events")
    given_on = models.DateField()
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    session = models.ForeignKey(
        "scheduling.OutreachSession", null=True, blank=True, on_delete=models.PROTECT, related_name="events"
    )
    lot = models.ForeignKey(
        "inventory.VaccineLot", null=True, blank=True, on_delete=models.PROTECT, related_name="events"
    )
    recorded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["child", "schedule_dose"], name="event_one_per_child_dose")
        ]
        indexes = [models.Index(fields=["facility", "given_on"], name="event_facility_date_idx")]
