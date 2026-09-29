"""Defaulter list (FR-20 to FR-22, BR-02, BR-04, BR-09) and sessions (FR-23, FR-24)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from apps.passport.models import Child, ImmunizationEvent, ScheduleDose
from apps.passport.services import DEFAULTER_MAX_AGE_DAYS, DoseState, DoseStatus, dose_statuses


@dataclass(frozen=True)
class Defaulter:
    child: Child
    overdue: list[DoseStatus]
    days_to_nearest_max_age: int

    @property
    def overdue_count(self) -> int:
        return len(self.overdue)


def defaulters(facility_id: int, on: date) -> list[Defaulter]:
    """Children under 2 registered at the facility with at least one overdue dose, ranked by BR-04."""
    schedule = list(ScheduleDose.objects.select_related("antigen"))
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


def rank(found: list[Defaulter]) -> list[Defaulter]:
    """BR-04: most overdue doses first, then nearest to an antigen's maximum age, then system ID."""
    return sorted(found, key=lambda d: (-d.overdue_count, d.days_to_nearest_max_age, d.child.system_id))
