from rest_framework import serializers
from rest_framework.generics import ListAPIView

from apps.accounts.permissions import IsSystemAdmin

from .models import Facility


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ["id", "code", "name", "keph_level", "ownership", "county", "sub_county", "is_synthetic"]


class FacilityAdminListView(ListAPIView):
    """Facility list for the system administrator (FR-03)."""

    permission_classes = [IsSystemAdmin]
    serializer_class = FacilitySerializer
    queryset = Facility.objects.order_by("code")
