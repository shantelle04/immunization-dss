from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import AuditAction, AuditLog, User

# Hash compared when the username does not exist, so a miss costs the same time as a wrong password.
_DUMMY_HASH = make_password("timing-equaliser-not-a-real-password")


class LoginRefused(Exception):
    """Generic refusal: the caller never learns whether the user exists, is locked or mistyped."""


def audit(
    user: User | None,
    action: str,
    entity: str,
    entity_id: str = "",
    facility=None,
    cross_facility: bool = False,
) -> None:
    AuditLog.objects.create(
        user=user,
        facility=facility if facility is not None else getattr(user, "facility", None),
        action=action,
        entity=entity,
        entity_id=str(entity_id)[:64],
        cross_facility=cross_facility,
    )


def authenticate_with_lockout(username: str, password: str) -> User:
    user = _attempt(username, password)
    if user is None:
        raise LoginRefused
    return user


@transaction.atomic
def _attempt(username: str, password: str) -> User | None:
    """Commits the failure count and audit entry even when the login is refused."""
    user = User.objects.select_for_update().filter(username=username).first()
    if user is None:
        check_password(password, _DUMMY_HASH)
        audit(None, AuditAction.LOGIN_FAILED, "user")
        return None
    now = timezone.now()
    if user.locked_until and user.locked_until > now:
        audit(user, AuditAction.LOGIN_FAILED, "user", user.pk)
        return None
    if not user.is_active or not user.check_password(password):
        user.failed_logins += 1
        if user.failed_logins >= settings.LOCKOUT_THRESHOLD:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_logins = 0
            audit(user, AuditAction.LOCKOUT, "user", user.pk)
        else:
            audit(user, AuditAction.LOGIN_FAILED, "user", user.pk)
        user.save(update_fields=["failed_logins", "locked_until", "updated_at"])
        return None
    user.failed_logins = 0
    user.locked_until = None
    user.last_login = now
    user.save(update_fields=["failed_logins", "locked_until", "last_login", "updated_at"])
    audit(user, AuditAction.LOGIN, "user", user.pk)
    return user
