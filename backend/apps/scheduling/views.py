from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditAction
from apps.accounts.permissions import ClinicalReadManagerWrite, FacilityScopedQuerysetMixin, IsClinical
from apps.accounts.services import audit
from apps.common import today

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
