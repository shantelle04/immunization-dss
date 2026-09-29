from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditAction
from apps.accounts.permissions import FacilityScopedQuerysetMixin, IsClinical
from apps.accounts.services import audit
from apps.common import today
from apps.inventory.models import VaccineLot
from apps.inventory.services import StockRefused

from . import services
from .models import Child, ScheduleDose, Sex


class ChildSerializer(serializers.ModelSerializer):
    registration_facility = serializers.CharField(source="registration_facility.code", read_only=True)

    class Meta:
        model = Child
        fields = [
            "id",
            "system_id",
            "given_name",
            "family_name",
            "sex",
            "date_of_birth",
            "caregiver_name",
            "registration_facility",
            "registered_on",
            "is_synthetic",
        ]
        read_only_fields = ["id", "system_id", "registration_facility", "registered_on", "is_synthetic"]


class RegisterSerializer(serializers.Serializer):
    given_name = serializers.CharField(max_length=80)
    family_name = serializers.CharField(max_length=80)
    sex = serializers.ChoiceField(choices=Sex.choices)
    date_of_birth = serializers.DateField()
    caregiver_name = serializers.CharField(max_length=120)
    confirm_new = serializers.BooleanField(default=False)

    def validate_date_of_birth(self, value):
        if value > today():
            raise serializers.ValidationError("The date of birth cannot be in the future.")
        return value


class ChildListView(FacilityScopedQuerysetMixin, ListAPIView):
    """Children registered at the user's own facility (FR-30); other facilities only via search (BR-08)."""

    permission_classes = [IsClinical]
    serializer_class = ChildSerializer
    queryset = Child.objects.select_related("registration_facility").order_by("-registered_on", "system_id")
    facility_field = "registration_facility"

    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        confirm_new = fields.pop("confirm_new")
        try:
            child = services.register(fields, request.user, confirm_new=confirm_new)
        except services.DuplicateSuspected as dup:
            return Response(
                {
                    "detail": "A child with this family name and date of birth is already registered here.",
                    "candidates": ChildSerializer(dup.candidates, many=True).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(ChildSerializer(child).data, status=status.HTTP_201_CREATED)


class SearchSerializer(serializers.Serializer):
    system_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    family_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("system_id"):
            return attrs
        if attrs.get("family_name") and attrs.get("date_of_birth"):
            return attrs
        raise serializers.ValidationError("Give a system ID, or a family name and a date of birth.")


class ChildSearchView(APIView):
    """Cross-facility search (FR-32, BR-08): exact match only, read-only, every result audited."""

    permission_classes = [IsClinical]

    def get(self, request):
        query = SearchSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        found = services.search(request.user, **query.validated_data)
        return Response(ChildSerializer(found, many=True).data)


def _child_for(request, pk) -> Child:
    child = get_object_or_404(Child.objects.select_related("registration_facility"), pk=pk)
    return child


class ChildDetailView(APIView):
    permission_classes = [IsClinical]

    def get(self, request, pk):
        child = _child_for(request, pk)
        cross = child.registration_facility_id != request.user.facility_id
        audit(request.user, AuditAction.READ, "child", child.pk, cross_facility=cross)
        return Response({**ChildSerializer(child).data, "read_only": cross})


class DoseSerializer(serializers.Serializer):
    dose_code = serializers.SlugRelatedField(slug_field="dose_code", queryset=ScheduleDose.objects.all())
    given_on = serializers.DateField()
    lot_number = serializers.CharField(max_length=32, required=False, allow_blank=True)


class ChildImmunizationsView(APIView):
    """History and next due doses (FR-33); recording a dose (FR-31) only at the user's own facility."""

    permission_classes = [IsClinical]

    def get(self, request, pk):
        child = _child_for(request, pk)
        cross = child.registration_facility_id != request.user.facility_id
        audit(request.user, AuditAction.READ, "immunizations", child.pk, cross_facility=cross)
        events = child.events.select_related("schedule_dose", "facility", "lot").order_by("given_on")
        statuses = services.child_statuses(child, today())
        return Response(
            {
                "child": ChildSerializer(child).data,
                "read_only": cross,
                "history": [
                    {
                        "dose_code": e.schedule_dose.dose_code,
                        "given_on": e.given_on,
                        "facility": e.facility.code,
                        "lot_number": e.lot.lot_number if e.lot_id else None,
                    }
                    for e in events
                ],
                "doses": [
                    {
                        "dose_code": s.dose_code,
                        "antigen": s.antigen,
                        "state": s.state,
                        "due_date": s.due_date,
                        "closes_on": s.closes_on,
                        "days_overdue": s.days_overdue,
                    }
                    for s in statuses
                    if s.state != services.DoseState.GIVEN
                ],
            }
        )

    def post(self, request, pk):
        child = _child_for(request, pk)
        if child.registration_facility_id != request.user.facility_id:
            raise PermissionDenied("Records from another facility are read-only here.")
        data = DoseSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        dose = data.validated_data["dose_code"]
        lot = None
        if data.validated_data.get("lot_number"):
            lot = VaccineLot.objects.filter(
                lot_number=data.validated_data["lot_number"], antigen=dose.antigen
            ).first()
            if lot is None:
                raise ValidationError({"lot_number": "Unknown lot for this vaccine."})
        try:
            event = services.record_dose(child, dose, data.validated_data["given_on"], lot, request.user)
        except (services.DoseRefused, StockRefused) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            {"dose_code": dose.dose_code, "given_on": event.given_on}, status=status.HTTP_201_CREATED
        )


class ScheduleView(APIView):
    permission_classes = [IsClinical]

    def get(self, request):
        return Response(
            list(
                ScheduleDose.objects.select_related("antigen").values(
                    "dose_code",
                    "antigen__code",
                    "dose_number",
                    "recommended_age_days",
                    "min_age_days",
                    "max_age_days",
                    "min_interval_days",
                )
            )
        )
