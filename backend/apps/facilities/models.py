from django.db import models

from apps.common import Timestamped


class KephLevel(models.TextChoices):
    DISPENSARY = "dispensary", "Dispensary"
    HEALTH_CENTRE = "health_centre", "Health centre"
    SUB_COUNTY_HOSPITAL = "sub_county_hospital", "Sub-county hospital"


class Facility(Timestamped):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=120)
    keph_level = models.CharField(max_length=24, choices=KephLevel.choices)
    ownership = models.CharField(max_length=24)
    county = models.CharField(max_length=60)
    sub_county = models.CharField(max_length=60)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(keph_level__in=KephLevel.values), name="facility_keph_level_valid"
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"
