"""Role permissions and facility scoping, checked before any view logic runs (fail closed)."""

from rest_framework.permissions import BasePermission

from .models import Role


def _active(request) -> bool:
    user = request.user
    return bool(user and user.is_authenticated and user.is_active)


class IsClinical(BasePermission):
    """Health worker or facility manager with a facility."""

    def has_permission(self, request, view) -> bool:
        return _active(request) and request.user.is_clinical and request.user.facility_id is not None


class IsFacilityManager(BasePermission):
    def has_permission(self, request, view) -> bool:
        return (
            _active(request)
            and request.user.role == Role.FACILITY_MANAGER
            and request.user.facility_id is not None
        )


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        return _active(request) and request.user.role == Role.SYSTEM_ADMIN


class ClinicalReadManagerWrite(BasePermission):
    """Clinical staff read; only the facility manager changes configuration-type resources."""

    def has_permission(self, request, view) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return IsClinical().has_permission(request, view)
        return IsFacilityManager().has_permission(request, view)


class FacilityScopedQuerysetMixin:
    """Every list and detail query is limited to the requesting user's facility.

    Views set `facility_field` to the lookup path of the owning facility.
    """

    facility_field = "facility"

    def get_queryset(self):
        return super().get_queryset().filter(**{self.facility_field: self.request.user.facility_id})
