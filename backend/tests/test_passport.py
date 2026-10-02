"""TC-U passport: dose status (FR-20, BR-01 to BR-03), registration (FR-30, FR-36), recording (FR-31)."""

from datetime import date, timedelta

import pytest
from conftest import client_for

from apps.inventory.services import balance
from apps.passport.models import ScheduleDose
from apps.passport.services import DoseState, dose_statuses


def _states(dob, given, on):
    schedule = list(ScheduleDose.objects.select_related("antigen"))
    return {s.dose_code: s for s in dose_statuses(dob, given, schedule, on)}


@pytest.mark.django_db
def test_due_then_overdue_after_28_days_grace(schedule):
    dob = date(2025, 1, 1)
    due_day = dob + timedelta(days=42)
    assert _states(dob, {}, due_day - timedelta(days=1))["PENTA-1"].state == DoseState.NOT_YET
    assert _states(dob, {}, due_day)["PENTA-1"].state == DoseState.DUE
    assert _states(dob, {}, due_day + timedelta(days=28))["PENTA-1"].state == DoseState.DUE
    late = _states(dob, {}, due_day + timedelta(days=29))["PENTA-1"]
    assert late.state == DoseState.OVERDUE and late.days_overdue == 29


@pytest.mark.django_db
def test_dose_closes_after_maximum_age(schedule):
    dob = date(2025, 1, 1)
    assert _states(dob, {}, dob + timedelta(days=106))["ROTA-1"].state == DoseState.CLOSED
    assert _states(dob, {}, dob + timedelta(days=15))["OPV-0"].state == DoseState.CLOSED


@pytest.mark.django_db
def test_interval_after_previous_dose_moves_the_due_date(schedule):
    dob = date(2025, 1, 1)
    late_first = dob + timedelta(days=80)
    status = _states(dob, {"PENTA-1": late_first}, dob + timedelta(days=90))["PENTA-2"]
    assert status.due_date == late_first + timedelta(days=28)
    assert status.state == DoseState.NOT_YET


@pytest.mark.django_db
def test_register_warns_about_duplicate_then_allows_confirmed_new(users, child_a):
    client = client_for(users["hcw_a"][0])
    body = {
        "given_name": "Baraka",
        "family_name": "otieno",
        "sex": "M",
        "date_of_birth": "2025-06-01",
        "caregiver_name": "Rehema Otieno",
    }
    dup = client.post("/api/v1/children", body, format="json")
    assert dup.status_code == 409 and dup.data["candidates"][0]["system_id"] == child_a.system_id
    new = client.post("/api/v1/children", {**body, "confirm_new": True}, format="json")
    assert new.status_code == 201 and new.data["system_id"] == "IMM-TST-A-00002"


@pytest.mark.django_db
def test_register_refuses_future_birth_date(users, schedule):
    client = client_for(users["hcw_a"][0])
    body = {"given_name": "A", "family_name": "B", "sex": "F", "caregiver_name": "C"}
    response = client.post("/api/v1/children", {**body, "date_of_birth": "2026-01-05"}, format="json")
    assert response.status_code == 400


def _record(client, child, dose, day):
    return client.post(f"/api/v1/children/{child.pk}/immunizations", {"dose_code": dose, "given_on": day})


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dose", "day", "reason"),
    [
        ("PENTA-1", "2025-07-01", "before 42 days"),
        ("ROTA-1", "2025-09-20", "after 105 days"),
        ("PENTA-1", "2026-01-10", "future"),
        ("BCG-1", "2025-05-01", "before birth"),
        ("PENTA-2", "2025-08-15", "previous dose missing"),
    ],
)
def test_record_dose_refuses_schedule_violations(users, child_a, stocked, dose, day, reason):
    response = _record(client_for(users["hcw_a"][0]), child_a, dose, day)
    assert response.status_code == 400, reason
    assert not child_a.events.exists()


@pytest.mark.django_db
def test_record_dose_issues_one_dose_and_refuses_a_second_copy(users, child_a, stocked, schedule, facility_a):
    client = client_for(users["hcw_a"][0])
    before = balance(facility_a.pk, schedule["PENTA"].pk)
    assert _record(client, child_a, "PENTA-1", "2025-07-15").status_code == 201
    assert balance(facility_a.pk, schedule["PENTA"].pk) == before - 1
    assert _record(client, child_a, "PENTA-1", "2025-07-20").status_code == 400
    assert balance(facility_a.pk, schedule["PENTA"].pk) == before - 1


@pytest.mark.django_db
def test_opv1_does_not_wait_for_the_optional_birth_dose(users, child_a, stocked):
    assert _record(client_for(users["hcw_a"][0]), child_a, "OPV-1", "2025-07-15").status_code == 201


@pytest.mark.django_db
def test_minimum_interval_between_doses(users, child_a, stocked):
    client = client_for(users["hcw_a"][0])
    assert _record(client, child_a, "PENTA-1", "2025-07-15").status_code == 201
    assert _record(client, child_a, "PENTA-2", "2025-08-10").status_code == 400
    assert _record(client, child_a, "PENTA-2", "2025-08-12").status_code == 201


@pytest.mark.django_db
def test_record_dose_without_stock_is_refused_and_leaves_no_event(users, child_a, schedule):
    response = _record(client_for(users["hcw_a"][0]), child_a, "BCG-1", "2025-06-02")
    assert response.status_code == 400 and "stock" in str(response.data).lower()
    assert not child_a.events.exists()


@pytest.mark.django_db
def test_history_lists_given_doses_and_open_ones(users, child_a, stocked):
    client = client_for(users["hcw_a"][0])
    _record(client, child_a, "BCG-1", "2025-06-02")
    data = client.get(f"/api/v1/children/{child_a.pk}/immunizations").data
    assert [h["dose_code"] for h in data["history"]] == ["BCG-1"]
    states = {d["dose_code"]: d["state"] for d in data["doses"]}
    assert "BCG-1" not in states
    assert states["OPV-0"] == "closed" and states["PENTA-1"] == "overdue"
