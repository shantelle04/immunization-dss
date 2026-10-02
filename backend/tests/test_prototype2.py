"""TC-I forecasts and alerts (FR-12 to FR-16), session plans and attendance (FR-23, FR-24), FHIR export
(FR-34), administration (FR-03) and the overview. No model is fitted here: runs use the baselines (D-14)."""

import json
from datetime import date, timedelta

import pytest
from conftest import TODAY, client_for

from apps.accounts.models import AuditAction, AuditLog
from apps.inventory import forecasting
from apps.inventory.models import AlertStatus, Forecast, StockAlert, StockPolicy, StockTransaction, TxKind
from apps.passport.models import Child, ImmunizationEvent
from apps.scheduling.models import OutreachSession, SessionAttendance

WEEKS = 40
FIRST_WEEK = TODAY - timedelta(weeks=WEEKS)


@pytest.fixture
def ledger(facility_a, facility_b, schedule):
    """40 weeks of steady use: BCG at facility A ends nearly empty, everything else is well stocked."""
    rows = []
    for facility in (facility_a, facility_b):
        for antigen in schedule.values():
            low = facility == facility_a and antigen.code == "BCG"
            rows.append(
                StockTransaction(
                    facility=facility,
                    antigen=antigen,
                    kind=TxKind.OPENING_BALANCE,
                    quantity_doses=WEEKS * 10 + (5 if low else 500),
                    occurred_on=FIRST_WEEK,
                )
            )
            rows += [
                StockTransaction(
                    facility=facility,
                    antigen=antigen,
                    kind=TxKind.ISSUE,
                    quantity_doses=-10,
                    occurred_on=FIRST_WEEK + timedelta(weeks=w, days=1),
                )
                for w in range(WEEKS)
            ]
            StockPolicy.objects.create(
                facility=facility, antigen=antigen, cycle_weeks=4, safety_buffer="0.25"
            )
    StockTransaction.objects.bulk_create(rows)


@pytest.mark.django_db
def test_run_forecasts_stores_four_weeks_per_series_and_raises_the_expected_alert(users, ledger):
    run = forecasting.run(TODAY)
    assert run.params["source"] == "baselines" and run.params["weeks"] == WEEKS
    assert Forecast.objects.filter(run=run).count() == 2 * 5 * 4
    assert set(Forecast.objects.values_list("week_start", flat=True)) == {
        TODAY + timedelta(weeks=i) for i in range(4)
    }
    alerts = list(StockAlert.objects.select_related("facility", "antigen"))
    assert [(a.facility.code, a.antigen.code, a.status) for a in alerts] == [("TST-A", "BCG", "open")]
    assert alerts[0].projected_doses < alerts[0].safety_minimum


@pytest.mark.django_db
def test_forecast_endpoint_shows_history_interval_model_and_accuracy(users, ledger):
    forecasting.run(TODAY)
    data = client_for(users["hcw_a"][0]).get("/api/v1/forecasts").data
    assert data["run"]["source"] == "baselines"
    bcg = next(a for a in data["antigens"] if a["antigen"] == "BCG")
    assert len(bcg["forecast"]) == 4 and len(bcg["history"]) == 26
    assert bcg["history"][-1]["issued"] == 10
    assert all(w["lo80"] <= w["yhat"] <= w["hi80"] for w in bcg["forecast"])
    assert bcg["model"] in ("seasonal_naive", "moving_average")
    assert set(bcg["accuracy"]) == {"model", "mase", "mae", "smape", "coverage80"}


@pytest.mark.django_db
def test_no_forecast_run_gives_an_empty_answer_not_an_error(users, stocked):
    data = client_for(users["hcw_a"][0]).get("/api/v1/forecasts").data
    assert data == {"run": None, "antigens": []}


@pytest.mark.django_db
def test_alert_is_acknowledged_by_the_manager_kept_on_the_next_run_and_resolved_after_a_receipt(
    users, ledger, schedule
):
    forecasting.run(TODAY)
    alert = StockAlert.objects.get()
    manager, worker = client_for(users["fm_a"][0]), client_for(users["hcw_a"][0])
    assert [a["antigen"] for a in worker.get("/api/v1/alerts").data["results"]] == ["BCG"]
    assert client_for(users["hcw_b"][0]).get("/api/v1/alerts").data["results"] == []
    assert worker.post(f"/api/v1/alerts/{alert.pk}/acknowledge").status_code == 403
    done = manager.post(f"/api/v1/alerts/{alert.pk}/acknowledge")
    assert done.status_code == 200 and done.data["status"] == "acknowledged"
    assert manager.post(f"/api/v1/alerts/{alert.pk}/acknowledge").status_code == 400

    forecasting.run(TODAY)
    alert.refresh_from_db()
    assert StockAlert.objects.count() == 1 and alert.status == AlertStatus.ACKNOWLEDGED

    StockTransaction.objects.create(
        facility=users["fm_a"][0].facility,
        antigen=schedule["BCG"],
        kind=TxKind.RECEIPT,
        quantity_doses=400,
        occurred_on=TODAY,
    )
    forecasting.run(TODAY)
    alert.refresh_from_db()
    assert alert.status == AlertStatus.RESOLVED
    assert manager.get("/api/v1/alerts").data["results"] == []
    assert len(manager.get("/api/v1/alerts", {"status": "resolved"}).data["results"]) == 1


@pytest.mark.django_db
def test_an_alert_of_another_facility_cannot_be_acknowledged(users, ledger, facility_b):
    forecasting.run(TODAY)
    alert = StockAlert.objects.get()
    other_manager = type(users["fm_a"][0]).objects.create_user(
        username="fm_b", password="a-long-test-password", role="facility_manager", facility=facility_b
    )
    assert client_for(other_manager).post(f"/api/v1/alerts/{alert.pk}/acknowledge").status_code == 404


@pytest.mark.django_db
def test_imported_results_are_refused_when_trained_on_other_data(users, ledger, tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"series_sha256": "0" * 64, "git_commit": "x"}))
    with pytest.raises(forecasting.ForecastRefused, match="different series"):
        forecasting.run(TODAY, tmp_path)
    assert not Forecast.objects.exists()


@pytest.mark.django_db
def test_stock_policy_is_read_by_staff_and_changed_only_by_the_manager(users, ledger):
    worker, manager = client_for(users["hcw_a"][0]), client_for(users["fm_a"][0])
    assert len(worker.get("/api/v1/stock/policies").data) == 5
    body = {"cycle_weeks": 2, "safety_buffer": "0.50"}
    assert worker.put("/api/v1/stock/policies/BCG", body, format="json").status_code == 403
    saved = manager.put("/api/v1/stock/policies/BCG", body, format="json")
    assert saved.status_code == 200 and saved.data["cycle_weeks"] == 2
    assert (
        manager.put("/api/v1/stock/policies/BCG", {**body, "cycle_weeks": 0}, format="json").status_code
        == 400
    )
    assert (
        manager.put("/api/v1/stock/policies/BCG", {**body, "safety_buffer": "9"}, format="json").status_code
        == 400
    )
    assert manager.put("/api/v1/stock/policies/NOPE", body, format="json").status_code == 404
    other = StockPolicy.objects.get(facility__code="TST-B", antigen__code="BCG")
    assert other.cycle_weeks == 4, "another facility's policy is untouched"


def _child(facility, n: int, born: date) -> Child:
    return Child.objects.create(
        system_id=f"IMM-{facility.code}-{n:05d}",
        given_name=f"Child{n}",
        family_name="Test",
        sex="F",
        date_of_birth=born,
        caregiver_name="Caregiver",
        registration_facility=facility,
        registered_on=born,
    )


@pytest.fixture
def defaulting(facility_a, stocked):
    """Two defaulters at facility A: the older one has missed more doses and ranks first."""
    older = _child(facility_a, 11, TODAY - timedelta(days=200))
    younger = _child(facility_a, 12, TODAY - timedelta(days=90))
    return older, younger


@pytest.mark.django_db
def test_session_plan_ranks_defaulters_lists_doses_and_compares_needs_with_stock(users, defaulting):
    older, younger = defaulting
    manager, worker = client_for(users["fm_a"][0]), client_for(users["hcw_a"][0])
    made = manager.post(
        "/api/v1/sessions",
        {"date": str(TODAY), "kind": "outreach", "location_name": "Market", "capacity": 1},
        format="json",
    )
    assert made.status_code == 201
    url = f"/api/v1/sessions/{made.data['id']}"
    assert worker.post(f"{url}/plan").status_code == 403
    plan = manager.post(f"{url}/plan").data
    assert [c["system_id"] for c in plan["children"]] == [older.system_id], "capacity 1 keeps the top rank"
    doses = {d["dose_code"] for d in plan["children"][0]["doses"]}
    assert {"PENTA-1", "OPV-1", "BCG-1"} <= doses and "MR-1" not in doses
    penta = next(n for n in plan["needs"] if n["antigen"] == "PENTA")
    assert penta["doses_planned"] == 1 and penta["in_stock_doses"] == 100 and penta["shortfall_doses"] == 0
    assert worker.get(url).data["children"] == plan["children"]
    assert client_for(users["hcw_b"][0]).get(url).status_code == 404


@pytest.mark.django_db
def test_session_dates_in_the_past_are_refused(users, stocked):
    response = client_for(users["fm_a"][0]).post(
        "/api/v1/sessions",
        {"date": str(TODAY - timedelta(days=1)), "kind": "outreach", "location_name": "X", "capacity": 5},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_attendance_records_doses_issues_stock_and_updates_the_defaulter_list(users, defaulting, schedule):
    older, younger = defaulting
    manager, worker = client_for(users["fm_a"][0]), client_for(users["hcw_a"][0])
    session = OutreachSession.objects.create(
        facility=users["fm_a"][0].facility, date=TODAY, kind="outreach", location_name="Market", capacity=10
    )
    url = f"/api/v1/sessions/{session.pk}"
    manager.post(f"{url}/plan")
    before = worker.get("/api/v1/defaulters").data["count"]
    done = worker.post(
        f"{url}/attendance",
        {"child_id": str(younger.pk), "attended": True, "doses": ["BCG-1", "PENTA-1", "OPV-1", "ROTA-1"]},
        format="json",
    )
    assert done.status_code == 201 and done.data["status"] == "held"
    row = next(c for c in done.data["children"] if c["system_id"] == younger.system_id)
    assert row["attended"] is True and {d["dose_code"] for d in row["doses"] if d["given"]} >= {
        "BCG-1",
        "PENTA-1",
    }
    assert ImmunizationEvent.objects.filter(child=younger, session=session).count() == 4
    balance = {r["antigen"]: r["balance_doses"] for r in worker.get("/api/v1/stock/balance").data["rows"]}
    assert balance["PENTA"] == 99 and balance["BCG"] == 99
    assert worker.get("/api/v1/defaulters").data["count"] == before - 1

    absent = worker.post(f"{url}/attendance", {"child_id": str(older.pk), "attended": False}, format="json")
    assert absent.status_code == 201
    assert SessionAttendance.objects.get(session=session, child=older).attended is False
    refused = worker.post(
        f"{url}/attendance", {"child_id": str(older.pk), "attended": False, "doses": ["BCG-1"]}, format="json"
    )
    assert refused.status_code == 400
    twice = worker.post(
        f"{url}/attendance",
        {"child_id": str(younger.pk), "attended": True, "doses": ["BCG-1"]},
        format="json",
    )
    assert twice.status_code == 400, "a dose already recorded is refused, and nothing else changes"
    assert ImmunizationEvent.objects.filter(child=younger).count() == 4


@pytest.mark.django_db
def test_attendance_is_refused_for_a_future_session_and_for_another_facilitys_child(
    users, defaulting, facility_b
):
    older, _ = defaulting
    worker = client_for(users["hcw_a"][0])
    future = OutreachSession.objects.create(
        facility=users["fm_a"][0].facility, date=TODAY + timedelta(days=3), kind="outreach", location_name="M"
    )
    body = {"child_id": str(older.pk), "attended": True}
    assert worker.post(f"/api/v1/sessions/{future.pk}/attendance", body, format="json").status_code == 400
    today_session = OutreachSession.objects.create(
        facility=users["fm_a"][0].facility, date=TODAY, kind="fixed", location_name="Clinic"
    )
    visitor = _child(facility_b, 21, TODAY - timedelta(days=100))
    response = worker.post(
        f"/api/v1/sessions/{today_session.pk}/attendance",
        {"child_id": str(visitor.pk), "attended": True},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_fhir_export_is_a_valid_shaped_bundle_and_every_export_is_audited(users, child_a, stocked):
    worker = client_for(users["hcw_a"][0])
    for dose, day in (("BCG-1", "2025-06-01"), ("OPV-0", "2025-06-02"), ("PENTA-1", "2025-07-14")):
        saved = worker.post(
            f"/api/v1/children/{child_a.pk}/immunizations",
            {"dose_code": dose, "given_on": day},
            format="json",
        )
        assert saved.status_code == 201
    response = worker.get(f"/api/v1/children/{child_a.pk}/fhir")
    assert response.status_code == 200 and "attachment" in response["Content-Disposition"]
    bundle = response.data
    assert bundle["resourceType"] == "Bundle" and bundle["type"] == "collection"
    patient = bundle["entry"][0]["resource"]
    assert patient["resourceType"] == "Patient" and patient["gender"] == "female"
    assert patient["birthDate"] == "2025-06-01" and patient["identifier"][0]["value"] == child_a.system_id
    immunizations = [e["resource"] for e in bundle["entry"][1:]]
    assert [i["vaccineCode"]["text"] for i in immunizations] == ["BCG-1", "OPV-0", "PENTA-1"]
    for resource in immunizations:
        assert resource["status"] == "completed"
        assert resource["patient"]["reference"] == bundle["entry"][0]["fullUrl"]
        assert resource["occurrenceDateTime"] and resource["vaccineCode"]["coding"][0]["code"]
    assert immunizations[1]["protocolApplied"][0] == {"series": "OPV", "doseNumberString": "0"}
    assert immunizations[2]["protocolApplied"][0]["doseNumberPositiveInt"] == 1
    assert len({e["fullUrl"] for e in bundle["entry"]}) == len(bundle["entry"])

    client_for(users["hcw_b"][0]).get(f"/api/v1/children/{child_a.pk}/fhir")
    exports = AuditLog.objects.filter(action=AuditAction.EXPORT).order_by("at")
    assert [e.cross_facility for e in exports] == [False, True]


@pytest.mark.django_db
def test_child_record_lists_every_scheduled_dose_with_its_state(users, child_a, stocked):
    record = client_for(users["hcw_a"][0]).get(f"/api/v1/children/{child_a.pk}/immunizations").data
    assert len(record["schedule"]) == 12
    assert {s["state"] for s in record["schedule"]} <= {"given", "not_yet", "due", "overdue", "closed"}


@pytest.mark.django_db
def test_overview_counts_match_the_lists(users, facility_a, ledger):
    _child(facility_a, 11, TODAY - timedelta(days=200))
    _child(facility_a, 12, TODAY - timedelta(days=90))
    forecasting.run(TODAY)
    worker = client_for(users["hcw_a"][0])
    data = worker.get("/api/v1/dashboard").data
    assert data["defaulters"] == worker.get("/api/v1/defaulters").data["count"] == 2
    assert data["children_under_two"] == 2
    assert data["alerts_open"] == 1 and data["alerts_acknowledged"] == 0
    assert data["next_session"] is None


@pytest.mark.django_db
def test_administrator_deactivates_resets_and_unlocks_accounts_but_not_their_own(users):
    admin_user, (worker, old_password) = users["sa"][0], users["hcw_a"]
    admin = client_for(admin_user)
    url = f"/api/v1/admin/users/{worker.pk}"
    assert admin.patch(url, {}, format="json").status_code == 400
    assert admin.patch(url, {"password": "short"}, format="json").status_code == 400
    off = admin.patch(url, {"is_active": False}, format="json")
    assert off.status_code == 200 and off.data["is_active"] is False and "password" not in off.data
    assert (
        client_for(None)
        .post("/api/v1/auth/login", {"username": worker.username, "password": old_password}, format="json")
        .status_code
        == 401
    )
    new_password = "a-new-long-passphrase-42"
    assert admin.patch(url, {"is_active": True, "password": new_password}, format="json").status_code == 200
    login = client_for(None).post(
        "/api/v1/auth/login", {"username": worker.username, "password": new_password}, format="json"
    )
    assert login.status_code == 200
    own = admin.patch(f"/api/v1/admin/users/{admin_user.pk}", {"is_active": False}, format="json")
    assert own.status_code == 400
    assert AuditLog.objects.filter(action=AuditAction.UPDATE, entity="user").count() == 2


@pytest.mark.django_db
def test_administrator_edits_the_schedule_within_ordered_age_limits(users, schedule):
    admin = client_for(users["sa"][0])
    assert len(admin.get("/api/v1/admin/schedule").data) == 12
    ok = admin.patch("/api/v1/admin/schedule/MR-1", {"max_age_days": 800}, format="json")
    assert ok.status_code == 200 and ok.data["max_age_days"] == 800
    assert admin.patch("/api/v1/admin/schedule/MR-1", {"max_age_days": 100}, format="json").status_code == 400
    assert admin.patch("/api/v1/admin/schedule/MR-1", {"min_age_days": -1}, format="json").status_code == 400
    assert admin.patch("/api/v1/admin/schedule/NOPE", {"max_age_days": 800}, format="json").status_code == 404
    renamed = admin.patch(
        "/api/v1/admin/schedule/MR-1", {"dose_code": "X", "max_age_days": 801}, format="json"
    )
    assert renamed.data["dose_code"] == "MR-1", "identifiers are read-only"


@pytest.mark.django_db
def test_administrator_creates_a_facility_and_sees_system_status_without_clinical_data(users, ledger):
    admin = client_for(users["sa"][0])
    body = {
        "code": "TST-C",
        "name": "Gamma Dispensary",
        "keph_level": "dispensary",
        "ownership": "public",
        "county": "C",
        "sub_county": "S",
    }
    assert admin.post("/api/v1/admin/facilities", body, format="json").status_code == 201
    assert admin.post("/api/v1/admin/facilities", body, format="json").status_code == 400, "codes are unique"
    assert (
        admin.post(
            "/api/v1/admin/facilities", {**body, "code": "D", "keph_level": "x"}, format="json"
        ).status_code
        == 400
    )
    forecasting.run(TODAY)
    overview = admin.get("/api/v1/admin/overview").data
    assert overview["facilities"] == 3 and overview["users_by_role"]["healthcare_worker"] == 2
    assert overview["forecast_run"]["source"] == "baselines"
    assert not {"children", "defaulters", "stock"} & set(overview)
