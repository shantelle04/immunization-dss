"""Demo upload files for one facility (FR-40): valid new rows plus a known set of planted errors.

Valid immunization rows are doses that are due or overdue today for the facility's children under 2, so they
are not yet in the registry and the import should accept them; each planted row breaks exactly one rule, and
the answer key says which. Nothing is written to the database.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from apps.common import today
from apps.facilities.models import Facility
from apps.passport.models import Antigen, Child
from apps.passport.services import DEFAULTER_MAX_AGE_DAYS, DoseState, child_statuses

from .services import IMMUNIZATION_COLUMNS, STOCK_COLUMNS

VALID_IMMUNIZATIONS = 20
VALID_STOCK = 8


def _csv(columns: list[str], rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _due_rows(facility: Facility, on: date) -> list[dict]:
    """The earliest due or overdue dose per antigen for each child under 2, given today."""
    rows = []
    children = Child.objects.filter(
        registration_facility=facility, date_of_birth__gt=on - timedelta(days=DEFAULTER_MAX_AGE_DAYS)
    ).order_by("system_id")
    for child in children.iterator():
        seen = set()
        for s in child_statuses(child, on):
            if s.state in (DoseState.DUE, DoseState.OVERDUE) and s.antigen not in seen:
                seen.add(s.antigen)
                rows.append(
                    {
                        "child_system_id": child.system_id,
                        "date_of_birth": child.date_of_birth.isoformat(),
                        "dose_code": s.dose_code,
                        "given_on": on.isoformat(),
                        "facility_code": facility.code,
                        "lot_number": "",
                    }
                )
        if len(rows) >= VALID_IMMUNIZATIONS:
            break
    return rows[:VALID_IMMUNIZATIONS]


def build(facility_code: str) -> dict[str, str]:
    """CSV text for immunizations, stock and the answer key."""
    facility = Facility.objects.get(code=facility_code)
    other = Facility.objects.exclude(pk=facility.pk).order_by("code").values_list("code", flat=True).first()
    on = today()
    valid = _due_rows(facility, on)
    if len(valid) < 2:
        raise ValueError(
            f"{facility_code} has fewer than two children with a due dose; pick another facility."
        )
    base = valid[0]
    planted = [
        ({**base, "child_system_id": ""}, "MISSING_CHILD_ID"),
        ({**base, "given_on": on.strftime("%d/%m/%Y")}, "MALFORMED_DATE"),
        ({**base, "dose_code": "XYZ-1"}, "UNKNOWN_DOSE"),
        ({**base, "facility_code": other or "NONE"}, "WRONG_FACILITY"),
        ({**base, "given_on": (on + timedelta(days=14)).isoformat()}, "FUTURE_DATE"),
        (
            {**base, "given_on": (date.fromisoformat(base["date_of_birth"]) - timedelta(days=3)).isoformat()},
            "DATE_BEFORE_BIRTH",
        ),
        ({**base, "child_system_id": f"IMM-{facility.code}-99999"}, "UNKNOWN_CHILD"),
        ({**valid[1], "date_of_birth": "2019-01-01"}, "BIRTH_DATE_MISMATCH"),
        (dict(base), "DUPLICATE_ROW"),
    ]
    immunizations = valid + [row for row, _ in planted]
    key = [
        {"file": "immunizations", "row_index": len(valid) + i, "defect": code}
        for i, (_, code) in enumerate(planted)
    ]

    antigens = list(Antigen.objects.order_by("code").values_list("code", flat=True))
    week = on - timedelta(days=on.weekday())
    stock_valid = [
        {
            "date": (week - timedelta(weeks=1 + i % 2)).isoformat(),
            "facility_code": facility.code,
            "antigen_code": antigens[i % len(antigens)],
            "lot_number": "",
            "kind": "receipt",
            "quantity_doses": str(20 * (1 + i % 3)),
        }
        for i in range(VALID_STOCK)
    ]
    sbase = stock_valid[0]
    stock_planted = [
        ({**sbase, "antigen_code": "XYZ"}, "UNKNOWN_ANTIGEN"),
        ({**sbase, "kind": "donation"}, "UNKNOWN_KIND"),
        ({**sbase, "quantity_doses": "twenty"}, "NON_NUMERIC_QUANTITY"),
        ({**sbase, "quantity_doses": "-20"}, "NEGATIVE_RECEIPT"),
        ({**sbase, "date": (on + timedelta(days=10)).isoformat()}, "FUTURE_DATE"),
        ({**sbase, "date": week.strftime("%d-%m-%Y")}, "MALFORMED_DATE"),
        ({**sbase, "facility_code": other or "NONE"}, "WRONG_FACILITY"),
    ]
    stock = stock_valid + [row for row, _ in stock_planted]
    key += [
        {"file": "stock", "row_index": len(stock_valid) + i, "defect": code}
        for i, (_, code) in enumerate(stock_planted)
    ]
    return {
        "immunizations": _csv(IMMUNIZATION_COLUMNS, immunizations),
        "stock": _csv(STOCK_COLUMNS, stock),
        "answer_key": _csv(["file", "row_index", "defect"], key),
    }
