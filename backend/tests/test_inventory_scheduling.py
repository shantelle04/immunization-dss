"""TC-U stock ledger (FR-10, FR-11, BR-06) and defaulter ranking (FR-21, FR-22, BR-04, BR-09)."""

from datetime import date

import pytest
from conftest import client_for
from django.db import IntegrityError

from apps.inventory.models import StockTransaction, TxKind
from apps.passport.models import Child, ImmunizationEvent, ScheduleDose
from apps.scheduling.services import defaulters


@pytest.mark.django_db
def test_quantity_sign_follows_the_kind(users, stocked):
    client = client_for(users["hcw_a"][0])
    wastage = client.post(
        "/api/v1/stock/transactions",
        {"antigen": "MR", "kind": "wastage", "quantity_doses": 7, "occurred_on": "2025-12-01"},
        format="json",
    )
    assert wastage.status_code == 201 and wastage.data["quantity_doses"] == -7
    receipt = client.post(
        "/api/v1/stock/transactions",
        {"antigen": "MR", "kind": "receipt", "quantity_doses": -20, "occurred_on": "2025-12-01"},
        format="json",
    )
    assert receipt.data["quantity_doses"] == 20


@pytest.mark.django_db
def test_stock_can_never_go_negative(users, stocked):
    response = client_for(users["hcw_a"][0]).post(
        "/api/v1/stock/transactions",
        {"antigen": "BCG", "kind": "issue", "quantity_doses": 101, "occurred_on": "2025-12-01"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_opening_balance_cannot_be_entered_by_hand(users, stocked):
    response = client_for(users["hcw_a"][0]).post(
        "/api/v1/stock/transactions",
        {"antigen": "BCG", "kind": "opening_balance", "quantity_doses": 5, "occurred_on": "2025-12-01"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_database_rejects_a_ledger_row_with_the_wrong_sign(facility_a, schedule):
    with pytest.raises(IntegrityError):
        StockTransaction.objects.create(
            facility=facility_a,
            antigen=schedule["BCG"],
            kind=TxKind.ISSUE,
            quantity_doses=5,
            occurred_on=date(2025, 1, 1),
        )


@pytest.mark.django_db
def test_balance_and_weeks_left(users, stocked, facility_a, schedule):
    StockTransaction.objects.create(
        facility=facility_a,
        antigen=schedule["BCG"],
        kind=TxKind.ISSUE,
        quantity_doses=-24,
        occurred_on=date(2025, 12, 1),
    )
    rows = {r["antigen"]: r for r in client_for(users["hcw_a"][0]).get("/api/v1/stock/balance").data["rows"]}
    assert rows["BCG"]["balance_doses"] == 76
    assert rows["BCG"]["weekly_use_doses"] == 2.0
    assert rows["BCG"]["weeks_left"] == 38.0
    assert rows["MR"]["weeks_left"] is None


def _child(facility, system_id, dob, given=()):
    child = Child.objects.create(
        system_id=system_id,
        given_name="G",
        family_name="F",
        sex="F",
        date_of_birth=dob,
        caregiver_name="C",
        registration_facility=facility,
        registered_on=dob,
    )
    for code, day in given:
        ImmunizationEvent.objects.create(
            child=child,
            schedule_dose=ScheduleDose.objects.get(dose_code=code),
            given_on=day,
            facility=facility,
        )
    return child


@pytest.mark.django_db
def test_defaulters_ranked_by_overdue_count_then_nearest_age_limit(facility_a, facility_b, schedule):
    on = date(2025, 12, 29)
    many = _child(facility_a, "IMM-TST-A-00010", date(2025, 6, 1))
    near_limit = _child(
        facility_a,
        "IMM-TST-A-00011",
        date(2025, 8, 20),
        given=[("BCG-1", date(2025, 8, 20)), ("OPV-0", date(2025, 8, 20)), ("PENTA-1", date(2025, 10, 1))],
    )
    _child(facility_a, "IMM-TST-A-00012", date(2023, 6, 1))  # over 2 years: outside the list (BR-09)
    _child(facility_b, "IMM-TST-B-00001", date(2025, 6, 1))  # other facility
    ranked = defaulters(facility_a.pk, on)
    assert [d.child.system_id for d in ranked] == [many.system_id, near_limit.system_id]
    assert ranked[0].overdue_count > ranked[1].overdue_count


@pytest.mark.django_db
def test_tie_on_count_goes_to_the_child_nearest_an_age_limit(facility_a, schedule):
    on = date(2025, 12, 29)
    older = _child(facility_a, "IMM-TST-A-00021", date(2025, 6, 1))
    younger = _child(facility_a, "IMM-TST-A-00020", date(2025, 7, 1))
    ranked = defaulters(facility_a.pk, on)
    assert ranked[0].overdue_count == ranked[1].overdue_count
    assert [d.child for d in ranked] == [older, younger]


@pytest.mark.django_db
def test_defaulter_api(users, child_a):
    data = client_for(users["hcw_a"][0]).get("/api/v1/defaulters").data
    assert data["count"] == 1 and data["results"][0]["system_id"] == child_a.system_id
