import secrets
from datetime import date

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.facilities.models import Facility
from apps.inventory.models import StockTransaction, TxKind
from apps.passport.models import Antigen, Child, ScheduleDose

# KEPI dose rules as in the synthetic dataset's schedule table (sim.yaml), with the BCG limit of D-24.
SCHEDULE = [
    ("BCG-1", "BCG", 1, "birth", 0, 0, 1795, 0),
    ("OPV-0", "OPV", 0, "birth", 0, 0, 14, 0),
    ("OPV-1", "OPV", 1, "w6", 42, 42, 365, 28),
    ("OPV-2", "OPV", 2, "w10", 70, 70, 365, 28),
    ("OPV-3", "OPV", 3, "w14", 98, 98, 365, 28),
    ("PENTA-1", "PENTA", 1, "w6", 42, 42, 365, 0),
    ("PENTA-2", "PENTA", 2, "w10", 70, 70, 365, 28),
    ("PENTA-3", "PENTA", 3, "w14", 98, 98, 365, 28),
    ("ROTA-1", "ROTA", 1, "w6", 42, 42, 105, 0),
    ("ROTA-2", "ROTA", 2, "w10", 70, 70, 168, 28),
    ("MR-1", "MR", 1, "m9", 274, 274, 730, 0),
    ("MR-2", "MR", 2, "m18", 548, 548, 1825, 28),
]
ANTIGENS = {"BCG": (20, False), "OPV": (20, True), "PENTA": (1, True), "ROTA": (1, True), "MR": (10, False)}
TODAY = date(2025, 12, 29)


@pytest.fixture(autouse=True)
def _clinical_today(settings):
    settings.IMMDSS_TODAY = TODAY.isoformat()
    cache.clear()  # throttle counters live in the cache


def password() -> str:
    return secrets.token_urlsafe(18)


@pytest.fixture
def facility_a(db):
    return Facility.objects.create(
        code="TST-A",
        name="Alpha Dispensary",
        keph_level="dispensary",
        ownership="public",
        county="C",
        sub_county="S",
    )


@pytest.fixture
def facility_b(db):
    return Facility.objects.create(
        code="TST-B",
        name="Beta Health Centre",
        keph_level="health_centre",
        ownership="public",
        county="C",
        sub_county="S",
    )


@pytest.fixture
def schedule(db):
    antigens = {
        code: Antigen.objects.create(code=code, name=code, doses_per_vial=dpv, open_vial_policy=ovp)
        for code, (dpv, ovp) in ANTIGENS.items()
    }
    for dose_code, antigen, number, contact, rec, lo, hi, interval in SCHEDULE:
        ScheduleDose.objects.create(
            dose_code=dose_code,
            antigen=antigens[antigen],
            dose_number=number,
            contact=contact,
            recommended_age_days=rec,
            min_age_days=lo,
            max_age_days=hi,
            min_interval_days=interval,
        )
    return antigens


@pytest.fixture
def users(facility_a, facility_b):
    made = {}
    for key, role, facility in [
        ("hcw_a", Role.HEALTHCARE_WORKER, facility_a),
        ("fm_a", Role.FACILITY_MANAGER, facility_a),
        ("hcw_b", Role.HEALTHCARE_WORKER, facility_b),
        ("sa", Role.SYSTEM_ADMIN, None),
    ]:
        pw = password()
        made[key] = (User.objects.create_user(username=key, password=pw, role=role, facility=facility), pw)
    return made


def client_for(user) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.fixture
def child_a(facility_a, schedule):
    return Child.objects.create(
        system_id="IMM-TST-A-00001",
        given_name="Amani",
        family_name="Otieno",
        sex="F",
        date_of_birth=date(2025, 6, 1),
        caregiver_name="Rehema Otieno",
        registration_facility=facility_a,
        registered_on=date(2025, 6, 1),
    )


@pytest.fixture
def stocked(facility_a, facility_b, schedule):
    for facility in (facility_a, facility_b):
        for antigen in schedule.values():
            StockTransaction.objects.create(
                facility=facility,
                antigen=antigen,
                kind=TxKind.RECEIPT,
                quantity_doses=100,
                occurred_on=date(2025, 1, 6),
            )
