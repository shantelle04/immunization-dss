import os
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User
from apps.facilities.models import Facility

CREDENTIALS = Path(settings.BASE_DIR).parent / ".demo_credentials.txt"


class Command(BaseCommand):
    help = (
        "Create the administrator (password from DJANGO_INITIAL_ADMIN_PASSWORD) and one manager and one "
        "health worker per facility with random passwords, written only to a git-ignored, owner-only file."
    )

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="give existing demo users new passwords")

    def handle(self, *args, reset: bool, **options):
        if not Facility.objects.exists():
            raise CommandError("No facilities: load a synthetic run first.")
        lines = []
        admin, created = User.objects.get_or_create(username="admin", defaults={"role": Role.SYSTEM_ADMIN})
        if created or reset:
            admin.set_password(os.environ["DJANGO_INITIAL_ADMIN_PASSWORD"])
            admin.save()
        lines.append("admin\tsystem_admin\t-\t(password: DJANGO_INITIAL_ADMIN_PASSWORD in .env)")
        for facility in Facility.objects.order_by("code"):
            for role, prefix in ((Role.FACILITY_MANAGER, "fm"), (Role.HEALTHCARE_WORKER, "hcw")):
                username = f"{prefix}-{facility.code.lower()}"
                user, created = User.objects.get_or_create(
                    username=username, defaults={"role": role, "facility": facility}
                )
                if created or reset:
                    password = secrets.token_urlsafe(12)
                    user.set_password(password)
                    user.save()
                    lines.append(f"{username}\t{role}\t{facility.code}\t{password}")
                else:
                    kept = "(unchanged; use --reset for a new one)"
                    lines.append(f"{username}\t{role}\t{facility.code}\t{kept}")
        fd = os.open(CREDENTIALS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("# Demo accounts for synthetic data only. Never commit or share this file.\n")
            fh.write("username\trole\tfacility\tpassword\n" + "\n".join(lines) + "\n")
        self.stdout.write(f"{len(lines)} accounts; credentials written to {CREDENTIALS.name} (owner-only)")
