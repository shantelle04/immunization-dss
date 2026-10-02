"""Prepare the end-to-end database: create it if missing, migrate, load the evidence run, run the baseline
forecasts and create the test accounts. The accounts' password comes from IMMDSS_E2E_PASSWORD, which the
runner generates for each run and never writes to disk.

Usage (from backend/): python -m evaluation.e2e_prepare <run_dir>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django
import psycopg
from psycopg import sql

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_e2e"
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.analytics_api.loader import load  # noqa: E402
from apps.common import today  # noqa: E402
from apps.facilities.models import Facility  # noqa: E402
from apps.inventory import forecasting  # noqa: E402
from apps.inventory.models import ForecastRun  # noqa: E402

ACCOUNTS = [
    ("e2e-hcw", Role.HEALTHCARE_WORKER, 0),
    ("e2e-fm", Role.FACILITY_MANAGER, 0),
    ("e2e-hcw-other", Role.HEALTHCARE_WORKER, 1),
    ("e2e-admin", Role.SYSTEM_ADMIN, None),
]


def ensure_database() -> None:
    db = settings.DATABASES["default"]
    with psycopg.connect(
        dbname="postgres",
        user=db["USER"],
        password=db["PASSWORD"],
        host=db["HOST"],
        port=db["PORT"],
        autocommit=True,
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [db["NAME"]]).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db["NAME"])))


def main() -> int:
    password = os.environ.get("IMMDSS_E2E_PASSWORD", "")
    if len(password) < 16:
        sys.exit("IMMDSS_E2E_PASSWORD must be set by the runner (at least 16 characters).")
    ensure_database()
    call_command("migrate", verbosity=0)
    if not Facility.objects.exists():
        load(Path(sys.argv[1]))
    if not ForecastRun.objects.exists():
        forecasting.run(today())
    facilities = list(Facility.objects.order_by("code")[:2])
    for username, role, index in ACCOUNTS:
        facility = None if index is None else facilities[index]
        user, _ = User.objects.get_or_create(username=username, defaults={"role": role, "facility": facility})
        user.set_password(password)
        user.is_active, user.failed_logins, user.locked_until = True, 0, None
        user.save()
    print(f"e2e database ready: {Facility.objects.count()} facilities, {len(ACCOUNTS)} test accounts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
