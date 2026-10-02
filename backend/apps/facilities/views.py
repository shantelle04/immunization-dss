from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from apps.accounts.models import AuditAction
from apps.accounts.permissions import IsSystemAdmin
from apps.accounts.services import audit

from .models import Facility


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ["id", "code", "name", "keph_level", "ownership", "county", "sub_county", "is_synthetic"]
        read_only_fields = ["id", "is_synthetic"]


class FacilityAdminListView(ListAPIView):
    """Facilities, listed and created by the system administrator (FR-03)."""

    permission_classes = [IsSystemAdmin]
    serializer_class = FacilitySerializer
    queryset = Facility.objects.order_by("code")

    def post(self, request):
        data = FacilitySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        facility = data.save()
        audit(request.user, AuditAction.CREATE, "facility", facility.pk, facility=facility)
        return Response(FacilitySerializer(facility).data, status=status.HTTP_201_CREATED)
