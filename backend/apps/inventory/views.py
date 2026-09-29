from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import FacilityScopedQuerysetMixin, IsClinical
from apps.common import today
from apps.passport.models import Antigen

from . import services
from .models import StockTransaction, TxKind, VaccineLot


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
