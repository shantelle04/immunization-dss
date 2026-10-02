"""Defaulter list (FR-20 to FR-22, BR-02, BR-04, BR-09) and sessions (FR-23, FR-24)."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import AuditAction, User
from apps.accounts.services import audit
from apps.common import today
from apps.inventory import services as inventory
from apps.inventory.models import Forecast, ForecastRun
from apps.passport import services as passport
from apps.passport.models import Antigen, Child, ImmunizationEvent, ScheduleDose
from apps.passport.services import DEFAULTER_MAX_AGE_DAYS, DoseState, DoseStatus, dose_statuses

from .models import OutreachSession, SessionAttendance, SessionPlanItem, SessionStatus

DEFAULT_CAPACITY = 30  # children planned when a session has no capacity set
DUE_SOON_DAYS = 7


@dataclass(frozen=True)
class Defaulter:
    child: Child
    overdue: list[DoseStatus]
    days_to_nearest_max_age: int

    @property
    def overdue_count(self) -> int:
        return len(self.overdue)


def _under_two(facility_id: int, on: date) -> tuple[list[Child], dict]:
    """Children under 2 registered at the facility (BR-09) and the doses each has received."""
    children = list(
        Child.objects.filter(
            registration_facility_id=facility_id,
            date_of_birth__gt=on - timedelta(days=DEFAULTER_MAX_AGE_DAYS),
            date_of_birth__lte=on,
        )
    )
    given: dict = defaultdict(dict)
    for child_id, dose_code, given_on in ImmunizationEvent.objects.filter(
        child__in=[c.pk for c in children], given_on__lte=on
    ).values_list("child_id", "schedule_dose__dose_code", "given_on"):
        given[child_id][dose_code] = given_on
    return children, given


def defaulters(facility_id: int, on: date) -> list[Defaulter]:
    """Children under 2 registered at the facility with at least one overdue dose, ranked by BR-04."""
    schedule = list(ScheduleDose.objects.select_related("antigen"))
    children, given = _under_two(facility_id, on)
    found = []
    for child in children:
        overdue = [
            s
            for s in dose_statuses(child.date_of_birth, given[child.pk], schedule, on)
            if s.state == DoseState.OVERDUE
        ]
        if overdue:
            nearest = min((s.closes_on - on).days for s in overdue)
            found.append(Defaulter(child, overdue, nearest))
    return rank(found)


def summary(facility_id: int, on: date) -> dict:
    """Counts for the overview screen: defaulters, children with a dose due, and doses due soon."""
    schedule = list(ScheduleDose.objects.select_related("antigen"))
    children, given = _under_two(facility_id, on)
    soon = on + timedelta(days=DUE_SOON_DAYS)
    defaulting = due_children = due_soon = 0
    for child in children:
        statuses = dose_statuses(child.date_of_birth, given[child.pk], schedule, on)
        states = {s.state for s in statuses}
        defaulting += DoseState.OVERDUE in states
        due_children += DoseState.DUE in states
        due_soon += sum(1 for s in statuses if s.state == DoseState.NOT_YET and s.due_date <= soon)
    return {
        "children_under_two": len(children),
        "defaulters": defaulting,
        "children_with_due_dose": due_children,
        "doses_due_in_7_days": due_soon,
    }


def rank(found: list[Defaulter]) -> list[Defaulter]:
    """BR-04: most overdue doses first, then nearest to an antigen's maximum age, then system ID."""
    return sorted(found, key=lambda d: (-d.overdue_count, d.days_to_nearest_max_age, d.child.system_id))


class SessionRefused(Exception):
    pass


@transaction.atomic
def generate_plan(session: OutreachSession, user: User) -> int:
    """FR-23: defaulters in BR-04 order up to the session capacity, each with the doses that can be given
    on the session date. Replaces an earlier plan of a session that has not been held."""
    if session.status != SessionStatus.PLANNED:
        raise SessionRefused("A session that has been held cannot be planned again.")
    if session.date < today():
        raise SessionRefused("The session date has passed.")
    schedule = {d.dose_code: d for d in ScheduleDose.objects.select_related("antigen")}
    children, given = _under_two(session.facility_id, session.date)
    ranked = defaulters(session.facility_id, today())[: session.capacity or DEFAULT_CAPACITY]
    by_id = {c.pk: c for c in children}
    session.plan_items.all().delete()
    items = []
    for position, d in enumerate(ranked, start=1):
        child = by_id.get(d.child.pk)
        if child is None:
            continue
        planned_antigens = set()
        statuses = dose_statuses(child.date_of_birth, given[child.pk], list(schedule.values()), session.date)
        # One dose per antigen: later doses of a series need the minimum interval after this one (BR-01).
        for s in sorted(statuses, key=lambda s: schedule[s.dose_code].dose_number):
            if s.state in (DoseState.DUE, DoseState.OVERDUE) and s.antigen not in planned_antigens:
                planned_antigens.add(s.antigen)
                items.append(
                    SessionPlanItem(
                        session=session,
                        child=child,
                        schedule_dose=schedule[s.dose_code],
                        priority_rank=position,
                    )
                )
    SessionPlanItem.objects.bulk_create(items)
    audit(user, AuditAction.UPDATE, "session_plan", session.pk)
    return len(items)


def session_detail(session: OutreachSession) -> dict:
    """Plan, vaccine needs against stock and forecast (FR-23), and attendance so far (FR-24)."""
    items = list(
        session.plan_items.select_related("child", "schedule_dose__antigen").order_by(
            "priority_rank", "schedule_dose__recommended_age_days"
        )
    )
    attended = dict(session.attendance.values_list("child_id", "attended"))
    given = defaultdict(set)
    for child_id, dose_code in session.events.values_list("child_id", "schedule_dose__dose_code"):
        given[child_id].add(dose_code)
    children: dict = {}
    doses_needed: dict[int, int] = defaultdict(int)
    for item in items:
        entry = children.setdefault(
            item.child_id,
            {
                "rank": item.priority_rank,
                "child_id": item.child_id,
                "system_id": item.child.system_id,
                "name": f"{item.child.given_name} {item.child.family_name}",
                "caregiver_name": item.child.caregiver_name,
                "date_of_birth": item.child.date_of_birth,
                "attended": attended.get(item.child_id),
                "doses": [],
            },
        )
        code = item.schedule_dose.dose_code
        entry["doses"].append({"dose_code": code, "given": code in given[item.child_id]})
        doses_needed[item.schedule_dose.antigen_id] += 1
    stock = {r["antigen"]: r["balance_doses"] for r in inventory.balances(session.facility_id, today())}
    week = session.date - timedelta(days=session.date.weekday())
    run = ForecastRun.objects.order_by("-run_at").first()
    forecast = (
        dict(
            Forecast.objects.filter(run=run, facility_id=session.facility_id, week_start=week)
            .values_list("antigen__code")
            .annotate(total=Sum("yhat"))
        )
        if run
        else {}
    )
    needs = []
    for antigen in Antigen.objects.filter(pk__in=doses_needed).order_by("code"):
        doses = doses_needed[antigen.pk]
        expected = float(forecast[antigen.code]) if antigen.code in forecast else None
        in_stock = stock.get(antigen.code, 0)
        needs.append(
            {
                "antigen": antigen.code,
                "antigen_name": antigen.name,
                "doses_planned": doses,
                "vials_planned": math.ceil(doses / antigen.doses_per_vial),
                "in_stock_doses": in_stock,
                "forecast_week_doses": expected,
                "shortfall_doses": max(0, doses - in_stock),
                "shortfall_with_forecast_doses": (
                    max(0, math.ceil(doses + expected - in_stock)) if expected is not None else None
                ),
            }
        )
    return {
        "id": session.pk,
        "date": session.date,
        "kind": session.kind,
        "location_name": session.location_name,
        "capacity": session.capacity,
        "status": session.status,
        "children": sorted(children.values(), key=lambda c: c["rank"]),
        "needs": needs,
    }


@transaction.atomic
def record_attendance(
    session: OutreachSession, child: Child, attended: bool, dose_codes: list[str], user: User
) -> None:
    """FR-24: mark attendance and record the doses given at the session (stock is issued per dose)."""
    if session.date > today():
        raise SessionRefused("Attendance can be recorded on or after the session date.")
    if child.registration_facility_id != session.facility_id:
        raise SessionRefused("This child is registered at another facility.")
    if dose_codes and not attended:
        raise SessionRefused("Doses can only be recorded for a child who attended.")
    SessionAttendance.objects.update_or_create(session=session, child=child, defaults={"attended": attended})
    for dose in ScheduleDose.objects.select_related("antigen").filter(dose_code__in=dose_codes):
        passport.record_dose(child, dose, session.date, None, user, session=session)
    if session.status != SessionStatus.HELD:
        session.status = SessionStatus.HELD
        session.save(update_fields=["status", "updated_at"])
    audit(user, AuditAction.UPDATE, "session_attendance", session.pk)
