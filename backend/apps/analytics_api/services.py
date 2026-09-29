"""CSV import validation (FR-40, NFR-08). Rules come from the data format and the schedule, never from the
planted-defect answer key; the key is used only afterwards to score them (score_import)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from apps.accounts.models import AuditAction, User
from apps.accounts.services import audit
from apps.common import today
from apps.facilities.models import Facility
from apps.inventory import services as inventory
from apps.inventory.models import INBOUND, TxKind, VaccineLot
from apps.passport import services as passport
from apps.passport.models import Antigen, Child, ImmunizationEvent, ScheduleDose

from .models import ImportBatch, ImportKind, ImportRowError

IMMUNIZATION_COLUMNS = [
    "child_system_id",
    "date_of_birth",
    "dose_code",
    "given_on",
    "facility_code",
    "lot_number",
]
STOCK_COLUMNS = ["date", "facility_code", "antigen_code", "lot_number", "kind", "quantity_doses"]
MAX_ROWS = 5000


class ImportRefused(Exception):
    pass


@dataclass
class Reference:
    """Codes the rows are checked against; `children` maps system ID to date of birth."""

    facilities: set[str]
    doses: set[str]
    antigens: set[str]
    children: dict[str, date]
    recorded: set[tuple[str, str]] = field(default_factory=set)
    own_facility: str | None = None

    @classmethod
    def from_database(cls, own_facility: str | None = None, check_existing: bool = True) -> Reference:
        recorded = set()
        if check_existing:
            recorded = set(
                ImmunizationEvent.objects.values_list("child__system_id", "schedule_dose__dose_code")
            )
        return cls(
            facilities=set(Facility.objects.values_list("code", flat=True)),
            doses=set(ScheduleDose.objects.values_list("dose_code", flat=True)),
            antigens=set(Antigen.objects.values_list("code", flat=True)),
            children=dict(Child.objects.values_list("system_id", "date_of_birth")),
            recorded=recorded,
            own_facility=own_facility,
        )


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def validate_immunizations(rows: list[dict], ref: Reference, on: date) -> dict[int, tuple[str, str]]:
    """First failing rule per row, as {row_index: (defect_code, message)}."""
    errors: dict[int, tuple[str, str]] = {}
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        child_id = (row.get("child_system_id") or "").strip()
        dose = (row.get("dose_code") or "").strip()
        facility = (row.get("facility_code") or "").strip()
        given, dob = _date(row.get("given_on", "")), _date(row.get("date_of_birth", ""))
        if not child_id:
            errors[i] = ("MISSING_CHILD_ID", "The child's system ID is empty.")
        elif given is None or dob is None:
            errors[i] = ("MALFORMED_DATE", "Dates must be written as YYYY-MM-DD.")
        elif dose not in ref.doses:
            errors[i] = ("UNKNOWN_DOSE", f"Unknown dose code '{dose[:12]}'.")
        elif facility not in ref.facilities:
            errors[i] = ("UNKNOWN_FACILITY", "Unknown facility code.")
        elif ref.own_facility and facility != ref.own_facility:
            errors[i] = ("WRONG_FACILITY", "Rows can only be imported for your own facility.")
        elif given > on:
            errors[i] = ("FUTURE_DATE", "The vaccination date is in the future.")
        elif given < dob:
            errors[i] = ("DATE_BEFORE_BIRTH", "The vaccination date is before the date of birth.")
        elif child_id not in ref.children:
            errors[i] = ("UNKNOWN_CHILD", "No registered child has this system ID.")
        elif ref.children[child_id] != dob:
            errors[i] = ("BIRTH_DATE_MISMATCH", "The date of birth differs from the registry.")
        elif (child_id, dose) in seen:
            errors[i] = ("DUPLICATE_ROW", "The same child and dose appear earlier in the file.")
        elif (child_id, dose) in ref.recorded:
            errors[i] = ("ALREADY_RECORDED", "This dose is already recorded for the child.")
        seen.add((child_id, dose))
    return errors


def validate_stock(rows: list[dict], ref: Reference, on: date) -> dict[int, tuple[str, str]]:
    errors: dict[int, tuple[str, str]] = {}
    for i, row in enumerate(rows):
        occurred = _date(row.get("date", ""))
        facility = (row.get("facility_code") or "").strip()
        antigen = (row.get("antigen_code") or "").strip()
        kind = (row.get("kind") or "").strip()
        raw_qty = (row.get("quantity_doses") or "").strip()
        if occurred is None:
            errors[i] = ("MALFORMED_DATE", "Dates must be written as YYYY-MM-DD.")
        elif facility not in ref.facilities:
            errors[i] = ("UNKNOWN_FACILITY", "Unknown facility code.")
        elif ref.own_facility and facility != ref.own_facility:
            errors[i] = ("WRONG_FACILITY", "Rows can only be imported for your own facility.")
        elif antigen not in ref.antigens:
            errors[i] = ("UNKNOWN_ANTIGEN", f"Unknown antigen code '{antigen[:8]}'.")
        elif kind not in TxKind.values or kind == TxKind.OPENING_BALANCE:
            errors[i] = ("UNKNOWN_KIND", "Unknown transaction kind.")
        elif not raw_qty.lstrip("-").isdigit():
            errors[i] = ("NON_NUMERIC_QUANTITY", "The quantity must be a whole number of doses.")
        elif kind in INBOUND and int(raw_qty) <= 0:
            errors[i] = ("NEGATIVE_RECEIPT", "A receipt must be a positive number of doses.")
        elif occurred > on:
            errors[i] = ("FUTURE_DATE", "The date is in the future.")
    return errors


def parse(upload: bytes, expected: list[str]) -> list[dict]:
    try:
        text = upload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportRefused("The file must be UTF-8 encoded CSV.") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != expected:
        raise ImportRefused(f"The columns must be exactly: {', '.join(expected)}.")
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise ImportRefused(f"At most {MAX_ROWS} rows per file.")
    return rows


def run_import(user: User, kind: str, upload: bytes, dry_run: bool) -> ImportBatch:
    """Validate every row; on a real run, commit the valid rows through the normal services."""
    columns = IMMUNIZATION_COLUMNS if kind == ImportKind.IMMUNIZATIONS else STOCK_COLUMNS
    rows = parse(upload, columns)
    ref = Reference.from_database(own_facility=user.facility.code)
    validate = validate_immunizations if kind == ImportKind.IMMUNIZATIONS else validate_stock
    errors = validate(rows, ref, today())
    if not dry_run:
        for i, row in enumerate(rows):
            if i in errors:
                continue
            try:
                _commit_row(user, kind, row)
            except (passport.DoseRefused, inventory.StockRefused) as exc:
                errors[i] = ("REFUSED", str(exc)[:200])
    with transaction.atomic():
        batch = ImportBatch.objects.create(
            facility_id=user.facility_id,
            uploaded_by=user,
            kind=kind,
            dry_run=dry_run,
            rows_total=len(rows),
            rows_rejected=len(errors),
        )
        ImportRowError.objects.bulk_create(
            ImportRowError(batch=batch, row_index=i, defect_code=code, message=msg)
            for i, (code, msg) in sorted(errors.items())
        )
        audit(user, AuditAction.CREATE, "import_batch", batch.pk)
    return batch


def _commit_row(user: User, kind: str, row: dict) -> None:
    lot_number = (row.get("lot_number") or "").strip()
    if kind == ImportKind.IMMUNIZATIONS:
        child = Child.objects.get(system_id=row["child_system_id"].strip())
        dose = ScheduleDose.objects.select_related("antigen").get(dose_code=row["dose_code"].strip())
        lot = (
            VaccineLot.objects.filter(lot_number=lot_number, antigen=dose.antigen).first()
            if lot_number
            else None
        )
        passport.record_dose(child, dose, date.fromisoformat(row["given_on"].strip()), lot, user)
    else:
        antigen = Antigen.objects.get(code=row["antigen_code"].strip())
        occurred = date.fromisoformat(row["date"].strip())
        lot = None
        if lot_number:
            lot, _ = VaccineLot.objects.get_or_create(
                lot_number=lot_number, defaults={"antigen": antigen, "first_received": occurred}
            )
        inventory.record(user, antigen, row["kind"].strip(), int(row["quantity_doses"]), occurred, lot)
