from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from apps.common import Timestamped


class Role(models.TextChoices):
    HEALTHCARE_WORKER = "healthcare_worker", "Healthcare worker"
    FACILITY_MANAGER = "facility_manager", "Facility manager"
    SYSTEM_ADMIN = "system_admin", "System administrator"


class UserManager(BaseUserManager):
    def create_user(self, username: str, password: str, role: str, facility=None, **extra) -> "User":
        user = self.model(username=username, role=role, facility=facility, **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, Timestamped):
    username = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=24, choices=Role.choices)
    facility = models.ForeignKey(
        "facilities.Facility", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    is_active = models.BooleanField(default=True)
    failed_logins = models.SmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["role"]

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=Role.values), name="user_role_valid"),
            # An administrator has no facility and no clinical scope; clinical roles always have one.
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.SYSTEM_ADMIN, facility__isnull=True)
                    | (~models.Q(role=Role.SYSTEM_ADMIN) & models.Q(facility__isnull=False))
                ),
                name="user_facility_matches_role",
            ),
        ]

    def __str__(self) -> str:
        return self.username

    @property
    def is_clinical(self) -> bool:
        return self.role in (Role.HEALTHCARE_WORKER, Role.FACILITY_MANAGER)


class AuditAction(models.TextChoices):
    CREATE = "create"
    UPDATE = "update"
    READ = "read"
    EXPORT = "export"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOCKOUT = "lockout"
    LOGOUT = "logout"


class AuditLog(Timestamped):
    at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="audit_entries")
    facility = models.ForeignKey("facilities.Facility", null=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=32, choices=AuditAction.choices)
    entity = models.CharField(max_length=48)
    entity_id = models.CharField(max_length=64)
    cross_facility = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["facility", "at"], name="audit_facility_at_idx")]
