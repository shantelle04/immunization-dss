"""Load a validated synthetic run's app/ folder into the database. truth/ is never read (doc 10 section 2)."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.db import connection, transaction

from apps.facilities.models import Facility
from apps.inventory.models import StockPolicy, StockTransaction, VaccineLot
from apps.passport.models import Antigen, Child, ImmunizationEvent, ScheduleDose
from apps.scheduling.models import OutreachSession, SessionStatus

APP_FILES = [
    "facilities",
    "antigens",
    "schedule",
    "vaccine_lots",
    "sessions",
    "children",
    "immunization_events",
    "stock_transactions",
]
HISTORIC_LOT = "HISTORIC"
BATCH = 5000
# D-24: the application uses the KEPI limit for BCG ("at birth and up to 59 months", Ministry of Health
# Kenya 2013, p. 30) instead of the simulator's one-year cut. 59 months = 1795 days (VERIFY the reading).
KEPI_OVERRIDES = {"BCG-1": {"max_age_days": 1795}}
# D-33: safety buffer for BR-05 until facility managers configure their own (ASSUMPTION).
DEFAULT_SAFETY_BUFFER = Decimal("0.25")

PROJECT_TABLES = [
    "scheduling_sessionattendance",
    "scheduling_sessionplanitem",
    "inventory_stockalert",
    "inventory_forecast",
    "inventory_forecastrun",
    "inventory_stockpolicy",
    "inventory_stocktransaction",
    "passport_immunizationevent",
    "scheduling_outreachsession",
    "passport_child",
    "inventory_vaccinelot",
    "passport_scheduledose",
    "passport_antigen",
]


class LoadRefused(Exception):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_run(run_dir: Path) -> dict:
    """The run must have passed validate-sim and its app/ files must match the manifest."""
    if "truth" in run_dir.resolve().parts:
        raise LoadRefused("Refusing a path inside truth/: evaluation data is never loaded.")
    manifest_path, report_path = run_dir / "manifest.json", run_dir / "validation_report.json"
    if not manifest_path.exists() or not report_path.exists():
        raise LoadRefused("Not a generated run: manifest.json or validation_report.json is missing.")
    if not json.loads(report_path.read_text()).get("passed"):
        raise LoadRefused("This run did not pass validate-sim; only validated runs can be loaded.")
    manifest = json.loads(manifest_path.read_text())
    for name in APP_FILES:
        rel = f"app/{name}.csv"
        if _sha256(run_dir / rel) != manifest["files"][rel]["sha256"]:
            raise LoadRefused(f"{rel} does not match its manifest hash.")
    return manifest


def _rows(run_dir: Path, name: str):
    with (run_dir / "app" / f"{name}.csv").open(newline="") as fh:
        yield from csv.DictReader(fh)


def _flag(value: str) -> bool:
    return value.strip().lower() == "true"


def _only_synthetic_data() -> bool:
    return not (
        Child.objects.filter(is_synthetic=False).exists()
        or ImmunizationEvent.objects.filter(is_synthetic=False).exists()
        or StockTransaction.objects.filter(is_synthetic=False).exists()
    )


@transaction.atomic
def load(run_dir: Path, replace: bool = False) -> dict[str, int]:
    manifest = check_run(run_dir)
    if Child.objects.exists():
        if not replace:
            raise LoadRefused("Data is already loaded; use --replace to reload synthetic data.")
        if not _only_synthetic_data():
            raise LoadRefused("Non-synthetic records exist; refusing to replace them.")
        with connection.cursor() as cursor:
            # Foreign keys are deferred; run pending checks now so TRUNCATE works inside this transaction.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute(f"TRUNCATE {', '.join(PROJECT_TABLES)} RESTART IDENTITY")
    counts: dict[str, int] = {}

    facilities = {}
    for r in _rows(run_dir, "facilities"):
        fac, _ = Facility.objects.update_or_create(
            code=r["facility_code"],
            defaults={
                "name": r["name"],
                "keph_level": r["keph_level"],
                "ownership": r["ownership"],
                "county": r["county"],
                "sub_county": r["sub_county"],
                "is_synthetic": _flag(r["is_synthetic"]),
            },
        )
        facilities[fac.code] = fac.pk
    counts["facilities"] = len(facilities)

    antigens = {
        r["antigen_code"]: Antigen.objects.create(
            code=r["antigen_code"],
            name=r["name"],
            doses_per_vial=int(r["doses_per_vial"]),
            open_vial_policy=_flag(r["open_vial_policy"]),
        ).pk
        for r in _rows(run_dir, "antigens")
    }
    counts["antigens"] = len(antigens)

    doses = {}
    for r in _rows(run_dir, "schedule"):
        fields = {
            "antigen_id": antigens[r["antigen_code"]],
            "dose_number": int(r["dose_number"]),
            "contact": r["contact"],
            "recommended_age_days": int(r["recommended_age_days"]),
            "min_age_days": int(r["min_age_days"]),
            "max_age_days": int(r["max_age_days"]),
            "min_interval_days": int(r["min_interval_days"]),
        }
        fields.update(KEPI_OVERRIDES.get(r["dose_code"], {}))
        doses[r["dose_code"]] = ScheduleDose.objects.create(dose_code=r["dose_code"], **fields).pk
    counts["schedule"] = len(doses)

    lots = {}
    for batch in _batched(
        VaccineLot(
            lot_number=r["lot_number"],
            antigen_id=antigens[r["antigen_code"]],
            first_received=date.fromisoformat(r["first_received"]),
        )
        for r in _rows(run_dir, "vaccine_lots")
    ):
        for lot in VaccineLot.objects.bulk_create(batch):
            lots[lot.lot_number] = lot.pk
    counts["vaccine_lots"] = len(lots)

    sessions = {}
    for batch in _batched(
        OutreachSession(
            source_ref=r["session_id"],
            facility_id=facilities[r["facility_code"]],
            date=date.fromisoformat(r["date"]),
            kind=r["kind"],
            location_name=r["location_name"],
            status=SessionStatus.HELD,
        )
        for r in _rows(run_dir, "sessions")
    ):
        for s in OutreachSession.objects.bulk_create(batch):
            sessions[s.source_ref] = s.pk
    counts["sessions"] = len(sessions)

    children = {}
    for batch in _batched(
        Child(
            source_ref=r["child_id"],
            system_id=r["system_id"],
            given_name=r["given_name"],
            family_name=r["family_name"],
            sex=r["sex"],
            date_of_birth=date.fromisoformat(r["date_of_birth"]),
            caregiver_name=r["caregiver_name"],
            registration_facility_id=facilities[r["registration_facility_code"]],
            registered_on=date.fromisoformat(r["registered_on"]),
            is_synthetic=_flag(r["is_synthetic"]),
        )
        for r in _rows(run_dir, "children")
    ):
        for c in Child.objects.bulk_create(batch):
            children[c.source_ref] = c.pk
    counts["children"] = len(children)

    counts["immunization_events"] = _bulk(
        ImmunizationEvent(
            source_ref=r["event_id"],
            child_id=children[r["child_id"]],
            schedule_dose_id=doses[r["dose_code"]],
            given_on=date.fromisoformat(r["given_on"]),
            facility_id=facilities[r["facility_code"]],
            session_id=sessions.get(r["session_id"]),
            lot_id=None if r["lot_number"] == HISTORIC_LOT else lots[r["lot_number"]],
            is_synthetic=_flag(r["is_synthetic"]),
        )
        for r in _rows(run_dir, "immunization_events")
    )
    counts["stock_transactions"] = _bulk(
        StockTransaction(
            source_ref=r["transaction_id"],
            facility_id=facilities[r["facility_code"]],
            antigen_id=antigens[r["antigen_code"]],
            lot_id=lots.get(r["lot_number"]),
            kind=r["kind"],
            quantity_doses=int(r["quantity_doses"]),
            occurred_on=date.fromisoformat(r["date"]),
            session_id=sessions.get(r["session_id"]) if r["session_id"] else None,
            is_synthetic=_flag(r["is_synthetic"]),
        )
        for r in _rows(run_dir, "stock_transactions")
    )

    cycle = int(json.loads((run_dir / "params.json").read_text())["stock"]["cycle_weeks"])
    StockPolicy.objects.bulk_create(
        StockPolicy(facility_id=f, antigen_id=a, cycle_weeks=cycle, safety_buffer=DEFAULT_SAFETY_BUFFER)
        for f in facilities.values()
        for a in antigens.values()
    )
    counts["stock_policies"] = len(facilities) * len(antigens)

    for name in APP_FILES:
        expected = manifest["files"][f"app/{name}.csv"]["rows"]
        if counts[name] != expected:
            raise LoadRefused(f"{name}: loaded {counts[name]} rows, manifest says {expected}.")
    counts["run_id"] = manifest["run_id"]
    return counts


def _batched(items):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def _bulk(items) -> int:
    total = 0
    for batch in _batched(items):
        model = type(batch[0])
        model.objects.bulk_create(batch)
        total += len(batch)
    return total
