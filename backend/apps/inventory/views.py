from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditAction
from apps.accounts.permissions import (
    ClinicalReadManagerWrite,
    FacilityScopedQuerysetMixin,
    IsClinical,
    IsFacilityManager,
)
from apps.accounts.services import audit
from apps.common import today
from apps.passport.models import Antigen

from . import services
from .models import AlertStatus, StockAlert, StockPolicy, StockTransaction, TxKind, VaccineLot


class TransactionSerializer(serializers.ModelSerializer):
    antigen = serializers.CharField(source="antigen.code", read_only=True)
    lot_number = serializers.CharField(source="lot.lot_number", read_only=True, default=None)

    class Meta:
        model = StockTransaction
        fields = ["id", "occurred_on", "antigen", "kind", "quantity_doses", "lot_number", "is_synthetic"]


class RecordSerializer(serializers.Serializer):
    antigen = serializers.SlugRelatedField(slug_field="code", queryset=Antigen.objects.all())
    kind = serializers.ChoiceField(choices=[k for k in TxKind.choices if k[0] != TxKind.OPENING_BALANCE])
    quantity_doses = serializers.IntegerField(min_value=-100000, max_value=100000)
    occurred_on = serializers.DateField()
    lot_number = serializers.CharField(max_length=32, required=False, allow_blank=True)


class TransactionListView(FacilityScopedQuerysetMixin, ListAPIView):
    """Stock ledger of the user's facility (FR-10); newest first, filter by antigen."""

    permission_classes = [IsClinical]
    serializer_class = TransactionSerializer
    queryset = StockTransaction.objects.select_related("antigen", "lot").order_by("-occurred_on", "-id")

    def get_queryset(self):
        qs = super().get_queryset()
        antigen = self.request.query_params.get("antigen", "")
        if antigen:
            if not Antigen.objects.filter(code=antigen).exists():
                raise ValidationError({"antigen": "Unknown antigen."})
            qs = qs.filter(antigen__code=antigen)
        return qs

    def post(self, request):
        data = RecordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        lot = None
        if v.get("lot_number"):
            lot, _ = VaccineLot.objects.get_or_create(
                lot_number=v["lot_number"],
                defaults={"antigen": v["antigen"], "first_received": v["occurred_on"]},
            )
            if lot.antigen_id != v["antigen"].id:
                raise ValidationError({"lot_number": "This lot belongs to another vaccine."})
        try:
            tx = services.record(
                request.user, v["antigen"], v["kind"], v["quantity_doses"], v["occurred_on"], lot
            )
        except services.StockRefused as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class BalanceView(APIView):
    """Current stock per antigen with weeks left (FR-11)."""

    permission_classes = [IsClinical]

    def get(self, request):
        return Response({"as_of": today(), "rows": services.balances(request.user.facility_id, today())})


class ForecastView(APIView):
    """4-week forecast per antigen with its 80% interval, model and backtest accuracy (FR-12, FR-15)."""

    permission_classes = [IsClinical]

    def get(self, request):
        return Response(services.forecast_overview(request.user.facility_id, today()))


class AlertSerializer(serializers.ModelSerializer):
    antigen = serializers.CharField(source="antigen.code", read_only=True)
    antigen_name = serializers.CharField(source="antigen.name", read_only=True)
    acknowledged_by = serializers.CharField(source="acknowledged_by.username", read_only=True, default=None)

    class Meta:
        model = StockAlert
        fields = [
            "id",
            "antigen",
            "antigen_name",
            "raised_on",
            "projected_breach_week",
            "projected_doses",
            "safety_minimum",
            "status",
            "acknowledged_by",
            "acknowledged_at",
        ]


class AlertListView(FacilityScopedQuerysetMixin, ListAPIView):
    """Stock-out alerts of the user's facility (FR-13); open and acknowledged unless ?status=resolved."""

    permission_classes = [IsClinical]
    serializer_class = AlertSerializer
    queryset = StockAlert.objects.select_related("antigen", "acknowledged_by").order_by(
        "projected_breach_week", "antigen__code"
    )

    def get_queryset(self):
        qs = super().get_queryset()
        wanted = self.request.query_params.get("status", "active")
        if wanted == "active":
            return qs.exclude(status=AlertStatus.RESOLVED)
        if wanted not in AlertStatus.values:
            raise ValidationError({"status": "Unknown status."})
        return qs.filter(status=wanted)


class AlertAcknowledgeView(APIView):
    """The facility manager acknowledges an open alert (FR-13)."""

    permission_classes = [IsFacilityManager]

    def post(self, request, pk):
        alert = get_object_or_404(
            StockAlert.objects.select_related("antigen"), pk=pk, facility_id=request.user.facility_id
        )
        if alert.status != AlertStatus.OPEN:
            raise ValidationError({"detail": "Only an open alert can be acknowledged."})
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])
        audit(request.user, AuditAction.UPDATE, "stock_alert", alert.pk)
        return Response(AlertSerializer(alert).data)


class PolicySerializer(serializers.ModelSerializer):
    antigen = serializers.CharField(source="antigen.code", read_only=True)
    antigen_name = serializers.CharField(source="antigen.name", read_only=True)
    cycle_weeks = serializers.IntegerField(min_value=1, max_value=12)
    safety_buffer = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=2)

    class Meta:
        model = StockPolicy
        fields = ["antigen", "antigen_name", "cycle_weeks", "safety_buffer"]


class PolicyListView(FacilityScopedQuerysetMixin, ListAPIView):
    """Replenishment cycle and safety buffer per antigen (FR-14)."""

    permission_classes = [IsClinical]
    serializer_class = PolicySerializer
    pagination_class = None
    queryset = StockPolicy.objects.select_related("antigen").order_by("antigen__code")


class PolicyDetailView(APIView):
    """Only the facility manager changes the stock policy of the facility (FR-14)."""

    permission_classes = [ClinicalReadManagerWrite]

    def _policy(self, request, code):
        antigen = get_object_or_404(Antigen, code=code)
        return StockPolicy.objects.select_related("antigen").filter(
            facility_id=request.user.facility_id, antigen=antigen
        ).first(), antigen

    def get(self, request, code):
        policy, antigen = self._policy(request, code)
        if policy is None:
            policy = StockPolicy(antigen=antigen, cycle_weeks=4, safety_buffer=services.DEFAULT_SAFETY_BUFFER)
        return Response(PolicySerializer(policy).data)

    def put(self, request, code):
        policy, antigen = self._policy(request, code)
        data = PolicySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        policy, _ = StockPolicy.objects.update_or_create(
            facility_id=request.user.facility_id, antigen=antigen, defaults=data.validated_data
        )
        audit(request.user, AuditAction.UPDATE, "stock_policy", policy.pk)
        return Response(PolicySerializer(policy).data)
