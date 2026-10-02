from django.shortcuts import get_object_or_404
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
from apps.inventory.models import AlertStatus, StockAlert
from apps.inventory.services import StockRefused, balances
from apps.passport.models import Child, ScheduleDose
from apps.passport.services import DoseRefused

from . import services
from .models import OutreachSession, SessionKind


class DefaulterListView(APIView):
    """Prioritised defaulter list for the user's facility (FR-21, FR-22)."""

    permission_classes = [IsClinical]

    def get(self, request):
        on = today()
        ranked = services.defaulters(request.user.facility_id, on)
        return Response(
            {
                "as_of": on,
                "count": len(ranked),
                "results": [
                    {
                        "rank": i,
                        "child_id": d.child.pk,
                        "system_id": d.child.system_id,
                        "name": f"{d.child.given_name} {d.child.family_name}",
                        "age_days": (on - d.child.date_of_birth).days,
                        "overdue_count": d.overdue_count,
                        "overdue": [s.dose_code for s in d.overdue],
                        "days_to_nearest_max_age": d.days_to_nearest_max_age,
                    }
                    for i, d in enumerate(ranked, start=1)
                ],
            }
        )


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutreachSession
        fields = ["id", "date", "kind", "location_name", "capacity", "status"]
        read_only_fields = ["id", "status"]

    def validate_kind(self, value):
        if value not in SessionKind.values:
            raise serializers.ValidationError("Unknown session kind.")
        return value

    def validate_date(self, value):
        if value < today():
            raise serializers.ValidationError("A new session cannot be in the past.")
        return value

    def validate_capacity(self, value):
        if value is not None and not 1 <= value <= 500:
            raise serializers.ValidationError("Capacity must be between 1 and 500.")
        return value


class SessionListView(FacilityScopedQuerysetMixin, ListAPIView):
    """Sessions of the user's facility; creating one is for the facility manager (FR-23)."""

    permission_classes = [ClinicalReadManagerWrite]
    serializer_class = SessionSerializer
    queryset = OutreachSession.objects.order_by("-date", "-id")

    def post(self, request):
        data = SessionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        session = data.save(facility_id=request.user.facility_id)
        audit(request.user, AuditAction.CREATE, "session", session.pk)
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


def _session_for(request, pk) -> OutreachSession:
    return get_object_or_404(OutreachSession, pk=pk, facility_id=request.user.facility_id)


class SessionDetailView(APIView):
    """One session of the user's facility with its plan, vaccine needs and attendance (FR-23, FR-24)."""

    permission_classes = [IsClinical]

    def get(self, request, pk):
        return Response(services.session_detail(_session_for(request, pk)))


class SessionPlanView(APIView):
    """The facility manager generates the outreach plan from the ranked defaulter list (FR-23)."""

    permission_classes = [IsFacilityManager]

    def post(self, request, pk):
        session = _session_for(request, pk)
        try:
            services.generate_plan(session, request.user)
        except services.SessionRefused as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(services.session_detail(session), status=status.HTTP_201_CREATED)


class AttendanceSerializer(serializers.Serializer):
    child_id = serializers.PrimaryKeyRelatedField(queryset=Child.objects.all(), source="child")
    attended = serializers.BooleanField()
    doses = serializers.ListField(
        child=serializers.SlugRelatedField(slug_field="dose_code", queryset=ScheduleDose.objects.all()),
        required=False,
        default=list,
        max_length=16,
    )


class SessionAttendanceView(APIView):
    """Attendance and the doses given at a session (FR-24); updates the child record and the ledger."""

    permission_classes = [IsClinical]

    def post(self, request, pk):
        session = _session_for(request, pk)
        data = AttendanceSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            services.record_attendance(
                session, v["child"], v["attended"], [d.dose_code for d in v["doses"]], request.user
            )
        except (services.SessionRefused, DoseRefused, StockRefused) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(services.session_detail(session), status=status.HTTP_201_CREATED)


class DashboardView(APIView):
    """Overview counts for the user's facility: stock, alerts, defaulters and the next session."""

    permission_classes = [IsClinical]

    def get(self, request):
        on = today()
        facility_id = request.user.facility_id
        stock = balances(facility_id, on)
        upcoming = (
            OutreachSession.objects.filter(facility_id=facility_id, date__gte=on).order_by("date").first()
        )
        alerts = StockAlert.objects.filter(facility_id=facility_id)
        return Response(
            {
                "as_of": on,
                **services.summary(facility_id, on),
                "alerts_open": alerts.filter(status=AlertStatus.OPEN).count(),
                "alerts_acknowledged": alerts.filter(status=AlertStatus.ACKNOWLEDGED).count(),
                "antigens_low_stock": sum(
                    1 for r in stock if r["weeks_left"] is not None and r["weeks_left"] < 2
                ),
                "antigens_out_of_stock": sum(1 for r in stock if r["balance_doses"] <= 0),
                "next_session": SessionSerializer(upcoming).data if upcoming else None,
            }
        )
