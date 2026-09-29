from django.db import models
from django.db.models import Q

from apps.common import Timestamped


class VaccineLot(Timestamped):
    lot_number = models.CharField(max_length=32, unique=True)
    antigen = models.ForeignKey("passport.Antigen", on_delete=models.PROTECT, related_name="lots")
    first_received = models.DateField()
    expiry = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return self.lot_number


class TxKind(models.TextChoices):
    OPENING_BALANCE = "opening_balance"
    RECEIPT = "receipt"
    ISSUE = "issue"
    WASTAGE = "wastage"
    LOSS = "loss"
    ADJUSTMENT = "adjustment"


INBOUND = (TxKind.OPENING_BALANCE, TxKind.RECEIPT)
OUTBOUND = (TxKind.ISSUE, TxKind.WASTAGE, TxKind.LOSS)


class StockTransaction(Timestamped):
    source_ref = models.CharField(max_length=16, unique=True, null=True, blank=True)
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    antigen = models.ForeignKey("passport.Antigen", on_delete=models.PROTECT, related_name="+")
    lot = models.ForeignKey(VaccineLot, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=16, choices=TxKind.choices)
    quantity_doses = models.IntegerField()
    occurred_on = models.DateField()
    session = models.ForeignKey(
        "scheduling.OutreachSession", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    recorded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["facility", "antigen", "occurred_on"], name="stocktx_facility_antigen_idx")
        ]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=TxKind.values), name="stocktx_kind_valid"),
            # Signed ledger: inbound rows add stock, outbound rows remove it; the balance is the sum.
            models.CheckConstraint(
                condition=Q(kind__in=INBOUND, quantity_doses__gte=0)
                | Q(kind__in=OUTBOUND, quantity_doses__lte=0)
                | Q(kind=TxKind.ADJUSTMENT),
                name="stocktx_sign_matches_kind",
            ),
        ]


class StockPolicy(Timestamped):
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    antigen = models.ForeignKey("passport.Antigen", on_delete=models.PROTECT, related_name="+")
    cycle_weeks = models.SmallIntegerField(default=4)
    safety_buffer = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "antigen"], name="stockpolicy_one_per_facility_antigen"
            ),
            models.CheckConstraint(condition=Q(safety_buffer__gte=0), name="stockpolicy_buffer_non_negative"),
        ]


class ForecastRun(Timestamped):
    run_at = models.DateTimeField()
    git_sha = models.CharField(max_length=40)
    data_sha256 = models.CharField(max_length=64)
    params = models.JSONField()
    metrics = models.JSONField(null=True, blank=True)


class ForecastModel(models.TextChoices):
    SEASONAL_NAIVE = "seasonal_naive"
    MOVING_AVERAGE = "moving_average"
    SARIMA = "sarima"
    GRU = "gru"
    POPULATION = "population"


class Forecast(Timestamped):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="forecasts")
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    antigen = models.ForeignKey("passport.Antigen", on_delete=models.PROTECT, related_name="+")
    week_start = models.DateField()
    horizon_week = models.SmallIntegerField()
    yhat = models.DecimalField(max_digits=10, decimal_places=2)
    lo80 = models.DecimalField(max_digits=10, decimal_places=2)
    hi80 = models.DecimalField(max_digits=10, decimal_places=2)
    model = models.CharField(max_length=16, choices=ForecastModel.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "facility", "antigen", "week_start"], name="forecast_one_per_run_series_week"
            ),
            models.CheckConstraint(
                condition=Q(horizon_week__gte=1, horizon_week__lte=4), name="forecast_horizon_1_4"
            ),
        ]


class AlertStatus(models.TextChoices):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class StockAlert(Timestamped):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="alerts")
    facility = models.ForeignKey("facilities.Facility", on_delete=models.PROTECT, related_name="+")
    antigen = models.ForeignKey("passport.Antigen", on_delete=models.PROTECT, related_name="+")
    raised_on = models.DateField()
    projected_breach_week = models.DateField()
    projected_doses = models.DecimalField(max_digits=10, decimal_places=2)
    safety_minimum = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=AlertStatus.choices, default=AlertStatus.OPEN)
    acknowledged_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["facility", "status"], name="alert_facility_status_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=AlertStatus.values), name="alert_status_valid")
        ]
