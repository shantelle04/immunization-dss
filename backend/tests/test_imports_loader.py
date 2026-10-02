"""TC-D import validation (FR-40, NFR-08) and the synthetic loader (app/ only, validated runs)."""

import csv
import hashlib
import io
import json
from datetime import date

import pytest
from conftest import client_for
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.analytics_api.loader import LoadRefused, load
from apps.analytics_api.services import Reference, validate_immunizations, validate_stock
from apps.passport.models import Child, ImmunizationEvent, ScheduleDose

ON = date(2025, 12, 29)
REF = Reference(
    facilities={"TST-A", "TST-B"},
    doses={"BCG-1", "PENTA-1"},
    antigens={"BCG", "PENTA"},
    children={"IMM-1": date(2025, 6, 1)},
)
GOOD = {
    "child_system_id": "IMM-1",
    "date_of_birth": "2025-06-01",
    "dose_code": "PENTA-1",
    "given_on": "2025-07-20",
    "facility_code": "TST-A",
    "lot_number": "",
}


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"child_system_id": ""}, "MISSING_CHILD_ID"),
        ({"given_on": "20/07/2025"}, "MALFORMED_DATE"),
        ({"dose_code": "HPV-1"}, "UNKNOWN_DOSE"),
        ({"facility_code": "NOPE"}, "UNKNOWN_FACILITY"),
        ({"given_on": "2026-02-01"}, "FUTURE_DATE"),
        ({"given_on": "2025-05-01"}, "DATE_BEFORE_BIRTH"),
        ({"child_system_id": "IMM-404"}, "UNKNOWN_CHILD"),
        ({"date_of_birth": "2025-06-02"}, "BIRTH_DATE_MISMATCH"),
    ],
)
def test_each_immunization_rule(change, code):
    errors = validate_immunizations([GOOD, {**GOOD, **change}], REF, ON)
    assert errors == {1: (code, errors[1][1])}


def test_duplicate_row_is_the_second_copy():
    errors = validate_immunizations([GOOD, dict(GOOD)], REF, ON)
    assert list(errors) == [1] and errors[1][0] == "DUPLICATE_ROW"


STOCK = {
    "date": "2025-11-03",
    "facility_code": "TST-A",
    "antigen_code": "BCG",
    "lot_number": "L1",
    "kind": "receipt",
    "quantity_doses": "40",
}


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"date": "03-11-2025"}, "MALFORMED_DATE"),
        ({"antigen_code": "YF"}, "UNKNOWN_ANTIGEN"),
        ({"quantity_doses": "forty"}, "NON_NUMERIC_QUANTITY"),
        ({"quantity_doses": "-40"}, "NEGATIVE_RECEIPT"),
        ({"kind": "gift"}, "UNKNOWN_KIND"),
        ({"date": "2026-01-02"}, "FUTURE_DATE"),
    ],
)
def test_each_stock_rule(change, code):
    errors = validate_stock([STOCK, {**STOCK, **change}], REF, ON)
    assert errors == {1: (code, errors[1][1])}


def _csv(rows, columns) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


@pytest.mark.django_db
def test_dry_run_reports_errors_and_changes_nothing(users, child_a):
    rows = [
        {**GOOD, "child_system_id": child_a.system_id},
        {**GOOD, "child_system_id": child_a.system_id, "facility_code": "TST-B"},
    ]
    upload = SimpleUploadedFile("imm.csv", _csv(rows, list(GOOD)), content_type="text/csv")
    response = client_for(users["fm_a"][0]).post(
        "/api/v1/imports", {"kind": "immunizations", "dry_run": True, "file": upload}, format="multipart"
    )
    assert response.status_code == 201
    assert response.data["rows_total"] == 2 and response.data["rows_rejected"] == 1
    assert response.data["errors"][0]["defect_code"] == "WRONG_FACILITY"
    assert not ImmunizationEvent.objects.exists()


@pytest.mark.django_db
def test_import_refuses_unexpected_columns(users, schedule):
    upload = SimpleUploadedFile("x.csv", b"a,b\n1,2\n", content_type="text/csv")
    response = client_for(users["fm_a"][0]).post(
        "/api/v1/imports", {"kind": "stock", "file": upload}, format="multipart"
    )
    assert response.status_code == 400


# ---------------------------------------------------------------- loader


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _tiny_run(root, passed=True):
    app = {
        "facilities": [
            {
                "facility_code": "SYN-D01",
                "name": "Olomani Dispensary",
                "keph_level": "dispensary",
                "ownership": "public",
                "county": "Synthetic County",
                "sub_county": "K",
                "is_synthetic": "True",
            }
        ],
        "antigens": [
            {"antigen_code": "BCG", "name": "BCG", "doses_per_vial": "20", "open_vial_policy": "False"}
        ],
        "schedule": [
            {
                "dose_code": "BCG-1",
                "antigen_code": "BCG",
                "dose_number": "1",
                "contact": "birth",
                "recommended_age_days": "0",
                "min_age_days": "0",
                "max_age_days": "365",
                "min_interval_days": "0",
            }
        ],
        "vaccine_lots": [
            {"lot_number": "BCG-2021-00001", "antigen_code": "BCG", "first_received": "2021-01-04"}
        ],
        "sessions": [
            {
                "session_id": "S0000001",
                "facility_code": "SYN-D01",
                "date": "2021-01-05",
                "kind": "fixed",
                "location_name": "Olomani Dispensary",
            }
        ],
        "children": [
            {
                "child_id": "C0000001",
                "system_id": "IMM-SYN-D01-00001",
                "given_name": "Neema",
                "family_name": "Waweru",
                "sex": "F",
                "date_of_birth": "2019-01-07",
                "caregiver_name": "Achieng Waweru",
                "registration_facility_code": "SYN-D01",
                "registered_on": "2019-01-07",
                "is_synthetic": "True",
            }
        ],
        "immunization_events": [
            {
                "event_id": "E00000001",
                "child_id": "C0000001",
                "dose_code": "BCG-1",
                "antigen_code": "BCG",
                "dose_number": "1",
                "given_on": "2019-01-07",
                "facility_code": "SYN-D01",
                "session_id": "S0000001",
                "lot_number": "HISTORIC",
                "is_synthetic": "True",
            }
        ],
        "stock_transactions": [
            {
                "transaction_id": "T00000001",
                "date": "2021-01-04",
                "facility_code": "SYN-D01",
                "antigen_code": "BCG",
                "lot_number": "BCG-2021-00001",
                "kind": "opening_balance",
                "quantity_doses": "20",
                "session_id": "",
                "is_synthetic": "True",
            }
        ],
    }
    files = {}
    for name, rows in app.items():
        path = root / "app" / f"{name}.csv"
        _write(path, rows)
        files[f"app/{name}.csv"] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (root / "manifest.json").write_text(json.dumps({"run_id": "sim-test", "files": files}))
    (root / "validation_report.json").write_text(json.dumps({"passed": passed}))
    (root / "params.json").write_text(json.dumps({"stock": {"cycle_weeks": 4}}))
    return root


@pytest.mark.django_db
def test_loads_app_folder_marks_synthetic_and_applies_kepi_bcg_limit(tmp_path):
    counts = load(_tiny_run(tmp_path / "run"))
    assert counts["children"] == 1 and counts["immunization_events"] == 1
    child = Child.objects.get()
    assert child.is_synthetic and child.source_ref == "C0000001"
    event = ImmunizationEvent.objects.get()
    assert event.lot is None, "HISTORIC maps to no lot"
    assert ScheduleDose.objects.get(dose_code="BCG-1").max_age_days == 1795


@pytest.mark.django_db
def test_refuses_unvalidated_runs_truth_paths_and_tampered_files(tmp_path):
    with pytest.raises(LoadRefused, match="did not pass"):
        load(_tiny_run(tmp_path / "failed", passed=False))
    truth = _tiny_run(tmp_path / "run" / "truth")
    with pytest.raises(LoadRefused, match="truth"):
        load(truth)
    tampered = _tiny_run(tmp_path / "tampered")
    with (tampered / "app" / "children.csv").open("a") as fh:
        fh.write("C0000002,IMM-X,A,B,F,2019-01-01,C,SYN-D01,2019-01-01,True\n")
    with pytest.raises(LoadRefused, match="manifest hash"):
        load(tampered)
    assert not Child.objects.exists()


@pytest.mark.django_db
def test_second_load_needs_replace(tmp_path):
    run = _tiny_run(tmp_path / "run")
    load(run)
    with pytest.raises(LoadRefused, match="--replace"):
        load(run)
    assert load(run, replace=True)["children"] == 1
    assert Child.objects.count() == 1
