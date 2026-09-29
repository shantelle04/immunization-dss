from django.db import models
from django.db.models import Q

from apps.common import Timestamped


class ImportKind(models.TextChoices):
    IMMUNIZATIONS = "immunizations"
    STOCK = "stock"


class ImportBatch(Timestamped):
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=16, choices=ImportKind.choices)
    dry_run = models.BooleanField()
    rows_total = models.IntegerField()
    rows_rejected = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=ImportKind.values), name="importbatch_kind_valid")
        ]


class ImportRowError(Timestamped):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="errors")
    row_index = models.IntegerField()
    defect_code = models.CharField(max_length=32)
    message = models.CharField(max_length=200)
