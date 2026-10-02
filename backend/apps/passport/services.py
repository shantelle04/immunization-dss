"""Health passport rules: dose status (FR-20, BR-01 to BR-03), registration (FR-30, FR-36), dose recording
(FR-31, BR-06), search (FR-32, BR-08)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.accounts.models import AuditAction, User
from apps.accounts.services import audit
from apps.common import today
from apps.facilities.models import Facility
from apps.inventory import services as inventory

from .models import Child, ImmunizationEvent, ScheduleDose

GRACE_DAYS = 28  # D-08: a due dose becomes overdue 28 days after its due date
DEFAULTER_MAX_AGE_DAYS = 730  # BR-09: the defaulter list covers children under 2 (scope D-01)


class DoseState:
    GIVEN = "given"
    NOT_YET = "not_yet"
    DUE = "due"
    OVERDUE = "overdue"
    CLOSED = "closed"


@dataclass(frozen=True)
class DoseStatus:
    dose_code: str
    antigen: str
    state: str
    due_date: date
    closes_on: date
    given_on: date | None = None
    days_overdue: int = 0


def dose_statuses(
    dob: date, given: dict[str, date], schedule: list[ScheduleDose], on: date
) -> list[DoseStatus]:
    """Status of every scheduled dose for a child born on `dob`, given the doses already received."""
    last_given: dict[int, date] = {}
    out = []
    for dose in sorted(schedule, key=lambda d: (d.antigen_id, d.dose_number)):
        closes_on = dob + timedelta(days=dose.max_age_days)
        due = dob + timedelta(days=dose.recommended_age_days)
        previous = last_given.get(dose.antigen_id)
        if previous is not None:
            due = max(due, previous + timedelta(days=dose.min_interval_days))
        given_on = given.get(dose.dose_code)
        if given_on is not None:
            state = DoseState.GIVEN
            last_given[dose.antigen_id] = given_on
        elif on > closes_on:
            state = DoseState.CLOSED
        elif on < due:
            state = DoseState.NOT_YET
        elif on <= due + timedelta(days=GRACE_DAYS):
            state = DoseState.DUE
        else:
            state = DoseState.OVERDUE
        overdue_days = (on - due).days if state == DoseState.OVERDUE else 0
        out.append(
            DoseStatus(dose.dose_code, dose.antigen.code, state, due, closes_on, given_on, overdue_days)
        )
    return sorted(out, key=lambda s: (s.due_date, s.dose_code))


def child_statuses(child: Child, on: date) -> list[DoseStatus]:
    schedule = list(ScheduleDose.objects.select_related("antigen"))
    given = dict(child.events.values_list("schedule_dose__dose_code", "given_on"))
    return dose_statuses(child.date_of_birth, given, schedule, on)


class DuplicateSuspected(Exception):
    def __init__(self, candidates: list[Child]):
        self.candidates = candidates


def next_system_id(facility) -> str:
    prefix = f"IMM-{facility.code}-"
    last = (
        Child.objects.filter(system_id__startswith=prefix).aggregate(m=Max("system_id"))["m"]
        or f"{prefix}00000"
    )
    return f"{prefix}{int(last.rsplit('-', 1)[1]) + 1:05d}"


@transaction.atomic
def register(data: dict, user: User, confirm_new: bool = False) -> Child:
    # Row lock on the facility serialises system ID allocation within a facility.
    facility = Facility.objects.select_for_update().get(pk=user.facility_id)
    if not confirm_new:
        candidates = list(
            Child.objects.filter(
                registration_facility=facility,
                family_name__iexact=data["family_name"],
                date_of_birth=data["date_of_birth"],
            )[:5]
        )
        if candidates:
            raise DuplicateSuspected(candidates)
    child = Child.objects.create(
        system_id=next_system_id(facility), registration_facility=facility, registered_on=today(), **data
    )
    audit(user, AuditAction.CREATE, "child", child.pk)
    return child


class DoseRefused(Exception):
    pass


@transaction.atomic
def record_dose(
    child: Child, dose: ScheduleDose, given_on: date, lot, user: User, session=None
) -> ImmunizationEvent:
    """Validate against the schedule (BR-01, BR-03, BR-06), record the event and issue one dose from stock."""
    if given_on > today():
        raise DoseRefused("The date cannot be in the future.")
    if given_on < child.date_of_birth:
        raise DoseRefused("The date is before the child's date of birth.")
    age = (given_on - child.date_of_birth).days
    if age < dose.min_age_days:
        raise DoseRefused(f"{dose.dose_code} cannot be given before {dose.min_age_days} days of age.")
    if age > dose.max_age_days:
        raise DoseRefused(f"{dose.dose_code} cannot be given after {dose.max_age_days} days of age.")
    previous = (
        child.events.filter(
            schedule_dose__antigen=dose.antigen, schedule_dose__dose_number__lt=dose.dose_number
        )
        .order_by("-schedule_dose__dose_number")
        .first()
    )
    # Dose n (n >= 2) needs dose n - 1; a birth dose (number 0, such as OPV-0) is optional.
    if dose.dose_number >= 2 and (
        previous is None or previous.schedule_dose.dose_number != dose.dose_number - 1
    ):
        raise DoseRefused(f"The previous dose of {dose.antigen.code} has not been recorded.")
    if previous and (given_on - previous.given_on).days < dose.min_interval_days:
        raise DoseRefused(f"At least {dose.min_interval_days} days are needed after the previous dose.")
    try:
        with transaction.atomic():
            event = ImmunizationEvent.objects.create(
                child=child,
                schedule_dose=dose,
                given_on=given_on,
                facility=user.facility,
                lot=lot,
                session=session,
                recorded_by=user,
            )
    except IntegrityError as exc:
        raise DoseRefused(f"{dose.dose_code} is already recorded for this child.") from exc
    inventory.issue_for_dose(user, dose.antigen, lot, given_on, session)
    audit(user, AuditAction.CREATE, "immunization_event", event.pk)
    return event


def search(user: User, system_id: str = "", family_name: str = "", date_of_birth: date | None = None):
    """Cross-facility search (BR-08): exact system ID, or family name and date of birth; reads are audited."""
    if system_id:
        found = list(Child.objects.filter(system_id=system_id).select_related("registration_facility"))
    else:
        found = list(
            Child.objects.filter(family_name__iexact=family_name, date_of_birth=date_of_birth).select_related(
                "registration_facility"
            )[:20]
        )
    for child in found:
        audit(
            user,
            AuditAction.READ,
            "child",
            child.pk,
            cross_facility=child.registration_facility_id != user.facility_id,
        )
    return found
