import contextlib

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from rest_framework import serializers, status
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.facilities.models import Facility

from .models import AuditAction, AuditLog, Role, User
from .permissions import FacilityScopedQuerysetMixin, IsFacilityManager, IsSystemAdmin
from .services import LoginRefused, audit, authenticate_with_lockout

REFUSED = "Username or password incorrect."


def _enforce_csrf(request) -> None:
    """Refresh and logout are authenticated by a cookie, so they need CSRF protection."""
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied("CSRF check failed.")


def _set_refresh_cookie(response: Response, refresh: RefreshToken) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
        path=settings.REFRESH_COOKIE_PATH,
    )


def _user_payload(user: User) -> dict:
    return {
        "username": user.username,
        "role": user.role,
        "facility": (
            {"code": user.facility.code, "name": user.facility.name, "level": user.facility.keph_level}
            if user.facility_id
            else None
        ),
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class PublicAuthView(APIView):
    """No authentication classes (the caller has no token yet), but refusals are still 401, not 403."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request) -> str:
        return 'Bearer realm="api"'


class LoginView(PublicAuthView):
    """Public by necessity (D-31): no token exists yet. Throttled, lockout, generic refusal."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            user = authenticate_with_lockout(data.validated_data["username"], data.validated_data["password"])
        except LoginRefused as exc:
            raise AuthenticationFailed(REFUSED) from exc
        refresh = RefreshToken.for_user(user)
        response = Response({"access": str(refresh.access_token), "user": _user_payload(user)})
        _set_refresh_cookie(response, refresh)
        get_token(request)  # sets the CSRF cookie used by refresh and logout
        return response


class RefreshView(PublicAuthView):
    """Public by necessity (D-31): the credential is the HttpOnly refresh cookie, rotated on use."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"

    def post(self, request):
        _enforce_csrf(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            raise AuthenticationFailed("Not signed in.")
        try:
            old = RefreshToken(raw)
            user = User.objects.select_related("facility").get(pk=old["user_id"], is_active=True)
            old.blacklist()
        except (TokenError, User.DoesNotExist, KeyError) as exc:
            raise AuthenticationFailed("Session expired.") from exc
        new = RefreshToken.for_user(user)
        response = Response({"access": str(new.access_token), "user": _user_payload(user)})
        _set_refresh_cookie(response, new)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _enforce_csrf(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw:
            # An expired or already revoked token still means the user is logged out.
            with contextlib.suppress(TokenError):
                RefreshToken(raw).blacklist()
        audit(request.user, AuditAction.LOGOUT, "user", request.user.pk)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict"
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))


class UserSerializer(serializers.ModelSerializer):
    facility = serializers.SlugRelatedField(
        slug_field="code", queryset=Facility.objects.all(), allow_null=True, required=False
    )
    password = serializers.CharField(write_only=True, min_length=12, max_length=256, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["id", "username", "role", "facility", "is_active", "password"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        is_admin = attrs.get("role") == Role.SYSTEM_ADMIN
        if is_admin == bool(attrs.get("facility")):
            raise serializers.ValidationError("Clinical roles need a facility; administrators have none.")
        candidate = User(username=attrs.get("username"), role=attrs.get("role"))
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserAdminListView(ListAPIView):
    """Users are created by the system administrator only; there is no self-registration (FR-01, FR-03)."""

    permission_classes = [IsSystemAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.select_related("facility").order_by("username")

    def post(self, request):
        data = UserSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = data.save()
        audit(request.user, AuditAction.CREATE, "user", user.pk, facility=user.facility)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class AuditEntrySerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", default=None)

    class Meta:
        model = AuditLog
        fields = ["at", "user", "action", "entity", "entity_id", "cross_facility"]


class AuditListView(FacilityScopedQuerysetMixin, ListAPIView):
    """The facility's audit log, for its manager (FR-41)."""

    permission_classes = [IsFacilityManager]
    serializer_class = AuditEntrySerializer
    queryset = AuditLog.objects.select_related("user").order_by("-at")
