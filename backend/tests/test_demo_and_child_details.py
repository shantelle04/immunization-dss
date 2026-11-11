"""Supervisor feedback (D-46, D-47): demonstration sign-in, sign-out after the access token expires, the
child's sex and age, and correcting a child's details. TC-SEC-12 to TC-SEC-15, TC-INT-30 to TC-INT-34."""

import secrets
from datetime import date

import pytest
from conftest import client_for
from django.conf import settings
from rest_framework.test import APIClient
from test_preflight import run_check, valid_env

from apps.accounts.models import AuditAction, AuditLog, Role, User
from apps.passport.models import ImmunizationEvent, ScheduleDose

DEMO = "/api/v1/auth/demo"
LOGOUT = "/api/v1/auth/logout"
REFRESH = "/api/v1/auth/refresh"


@pytest.fixture
def demo_on(settings):
    settings.DEMO_LOGIN = True


@pytest.fixture
def demo_users(facility_a):
    made = {}
    for name, role, facility in [
        ("demo-hcw", Role.HEALTHCARE_WORKER, facility_a),
        ("demo-admin", Role.SYSTEM_ADMIN, None),
    ]:
        made[name] = User.objects.create_user(
            username=name, password=secrets.token_urlsafe(18), role=role, facility=facility, is_demo=True
        )
    return made


@pytest.mark.django_db
def test_demo_sign_in_is_absent_when_switched_off(users, demo_users):
    client = APIClient()
    assert client.get(DEMO).status_code == 404
    assert client.post(DEMO, {"username": "demo-hcw"}, format="json").status_code == 404
    assert settings.DEMO_LOGIN is False, "the default must be off"


@pytest.mark.django_db
def test_demo_lists_only_demo_accounts(demo_on, users, demo_users):
    names = [a["username"] for a in APIClient().get(DEMO).data["accounts"]]
    assert sorted(names) == ["demo-admin", "demo-hcw"]
    assert "hcw_a" not in names, "real accounts are never offered"


@pytest.mark.django_db
def test_demo_sign_in_issues_a_normal_session(demo_on, demo_users):
    client = APIClient()
    response = client.post(DEMO, {"username": "demo-hcw"}, format="json")
    assert response.status_code == 200 and response.data["user"]["role"] == "healthcare_worker"
    assert response.cookies[settings.REFRESH_COOKIE_NAME]["httponly"]
    assert AuditLog.objects.filter(user=demo_users["demo-hcw"], action=AuditAction.LOGIN).exists()
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert me.get("/api/v1/auth/me").data["username"] == "demo-hcw"


@pytest.mark.django_db
@pytest.mark.parametrize("username", ["hcw_a", "sa", "nobody"])
def test_demo_sign_in_refuses_real_or_unknown_accounts(demo_on, users, username):
    response = APIClient().post(DEMO, {"username": username}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_demo_sign_in_refuses_a_deactivated_demo_account(demo_on, demo_users):
    User.objects.filter(username="demo-hcw").update(is_active=False)
    assert APIClient().post(DEMO, {"username": "demo-hcw"}, format="json").status_code == 401


@pytest.mark.django_db
def test_demo_sign_in_is_throttled(demo_on, demo_users):
    client = APIClient()
    codes = [client.post(DEMO, {"username": "demo-hcw"}, format="json").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[-1] == 429


def test_django_refuses_demo_sign_in_on_a_real_host(tmp_path):
    env = {**valid_env(), "IMMDSS_DEMO_LOGIN": "true", "DJANGO_ALLOWED_HOSTS": "dss.example.org"}
    result = run_check(env, tmp_path)
    assert result.returncode != 0 and "IMMDSS_DEMO_LOGIN" in result.stderr


def test_django_allows_demo_sign_in_on_this_computer(tmp_path):
    env = {**valid_env(), "IMMDSS_DEMO_LOGIN": "true", "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1"}
    assert run_check(env, tmp_path).returncode == 0


@pytest.mark.django_db
def test_sign_out_works_after_the_access_token_expired(users):
    _, pw = users["hcw_a"]
    client = APIClient()
    client.post("/api/v1/auth/login", {"username": "hcw_a", "password": pw}, format="json")
    refresh = client.cookies[settings.REFRESH_COOKIE_NAME].value
    response = client.post(LOGOUT)  # no access token at all, as after it expires
    assert response.status_code == 204
    assert response.cookies[settings.REFRESH_COOKIE_NAME].value == "", "the cookie must be cleared"
    replay = APIClient()
    replay.cookies[settings.REFRESH_COOKIE_NAME] = refresh
    assert replay.post(REFRESH).status_code == 401, "a reload must not sign the old user back in"
    assert AuditLog.objects.filter(user=users["hcw_a"][0], action=AuditAction.LOGOUT).exists()


@pytest.mark.django_db
def test_sign_out_without_a_session_is_harmless():
    response = APIClient().post(LOGOUT)
    assert response.status_code == 204 and not AuditLog.objects.filter(action=AuditAction.LOGOUT).exists()


@pytest.mark.django_db
def test_child_records_carry_sex_and_age_on_the_clinical_date(users, child_a):
    data = client_for(users["hcw_a"][0]).get(f"/api/v1/children/{child_a.pk}").data
    assert data["sex"] == "F"
    assert data["age_days"] == (date(2025, 12, 29) - date(2025, 6, 1)).days


@pytest.mark.django_db
def test_defaulters_carry_sex_and_age(users, child_a):
    rows = client_for(users["hcw_a"][0]).get("/api/v1/defaulters").data["results"]
    row = next(r for r in rows if r["system_id"] == child_a.system_id)
    assert row["sex"] == "F" and row["age_days"] == 211


@pytest.mark.django_db
def test_health_worker_corrects_a_childs_details(users, child_a):
    response = client_for(users["hcw_a"][0]).patch(
        f"/api/v1/children/{child_a.pk}", {"sex": "M", "caregiver_name": "Juma Otieno"}, format="json"
    )
    assert response.status_code == 200 and response.data["sex"] == "M"
    child_a.refresh_from_db()
    assert (child_a.sex, child_a.caregiver_name) == ("M", "Juma Otieno")
    edits = AuditLog.objects.filter(action=AuditAction.UPDATE, entity="child", entity_id=str(child_a.pk))
    assert edits.exists()


@pytest.mark.django_db
def test_another_facility_cannot_edit_the_child(users, child_a):
    response = client_for(users["hcw_b"][0]).patch(
        f"/api/v1/children/{child_a.pk}", {"sex": "M"}, format="json"
    )
    assert response.status_code == 403
    child_a.refresh_from_db()
    assert child_a.sex == "F"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [{}, {"sex": "X"}, {"date_of_birth": "2026-01-05"}, {"given_name": ""}, {"date_of_birth": "not-a-date"}],
)
def test_child_edit_validation(users, child_a, body):
    response = client_for(users["hcw_a"][0]).patch(f"/api/v1/children/{child_a.pk}", body, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_date_of_birth_correction_must_keep_recorded_doses_valid(users, child_a, facility_a):
    ImmunizationEvent.objects.create(
        child=child_a,
        schedule_dose=ScheduleDose.objects.get(dose_code="OPV-0"),
        given_on=date(2025, 6, 1),
        facility=facility_a,
        recorded_by=users["hcw_a"][0],
    )
    client = client_for(users["hcw_a"][0])
    moved = client.patch(f"/api/v1/children/{child_a.pk}", {"date_of_birth": "2025-05-01"}, format="json")
    assert moved.status_code == 400 and "OPV-0" in moved.data["date_of_birth"][0]
    small = client.patch(f"/api/v1/children/{child_a.pk}", {"date_of_birth": "2025-05-25"}, format="json")
    assert small.status_code == 200 and small.data["date_of_birth"] == "2025-05-25"


def test_environment_example_leaves_demo_sign_in_off():
    example = (settings.BASE_DIR.parent / ".env.example").read_text()
    assert "IMMDSS_DEMO_LOGIN=true" not in example


@pytest.mark.django_db
def test_seed_marks_demo_accounts_and_keeps_written_passwords(facility_a, tmp_path, monkeypatch):
    from django.core.management import call_command

    from apps.accounts.management.commands import seed_demo_users

    target = tmp_path / "demo.txt"
    monkeypatch.setattr(seed_demo_users, "CREDENTIALS", target)
    monkeypatch.setenv("DJANGO_INITIAL_ADMIN_PASSWORD", secrets.token_urlsafe(16))
    User.objects.create_user(
        username="fm-tst-a", password="x" * 16, role=Role.FACILITY_MANAGER, facility=facility_a
    )
    call_command("seed_demo_users")
    first = target.read_text()
    assert set(User.objects.filter(is_demo=True).values_list("username", flat=True)) == {
        "admin",
        "fm-tst-a",
        "hcw-tst-a",
    }
    hcw_password = next(ln.split("\t")[3] for ln in first.splitlines() if ln.startswith("hcw-tst-a"))
    call_command("seed_demo_users")
    second = target.read_text()
    assert f"hcw-tst-a\thealthcare_worker\tTST-A\t{hcw_password}" in second, "a rerun must not lose passwords"
    assert User.objects.get(username="hcw-tst-a").check_password(hcw_password)
