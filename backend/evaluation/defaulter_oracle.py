"""Defaulter oracle (doc 05 section 3): the rule re-implemented independently of the application code.

It reads the children and doses from the run's app/ CSV files and only the schedule table from the database,
works on whole columns with pandas (the application loops child by child), and returns for one facility the
ranked defaulter list the rule implies. The walkthrough compares it with the API for every facility.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from apps.passport.models import ScheduleDose

OVERDUE_AFTER_DAYS = 28  # BR-02
LIST_UNDER_DAYS = 730  # BR-09


def load(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    children = pd.read_csv(run_dir / "app" / "children.csv", parse_dates=["date_of_birth"])
    events = pd.read_csv(run_dir / "app" / "immunization_events.csv", parse_dates=["given_on"])
    schedule = pd.DataFrame(
        ScheduleDose.objects.values(
            "dose_code",
            "antigen__code",
            "dose_number",
            "recommended_age_days",
            "max_age_days",
            "min_interval_days",
        )
    ).sort_values(["antigen__code", "dose_number"])
    return children, events, schedule


def expected(children: pd.DataFrame, events: pd.DataFrame, schedule: pd.DataFrame, facility: str, on: date):
    """[(system_id, [overdue dose codes]), ...] in BR-04 order for one facility."""
    now = pd.Timestamp(on)
    age = (now - children["date_of_birth"]).dt.days
    kids = children[
        (children["registration_facility_code"] == facility) & (age >= 0) & (age < LIST_UNDER_DAYS)
    ].set_index("child_id")
    given = (
        events[events["child_id"].isin(kids.index) & (events["given_on"] <= now)]
        .pivot(index="child_id", columns="dose_code", values="given_on")
        .reindex(index=kids.index, columns=schedule["dose_code"])
    )
    overdue = pd.DataFrame(False, index=kids.index, columns=schedule["dose_code"])
    closes = pd.DataFrame(index=kids.index, columns=schedule["dose_code"], dtype="datetime64[ns]")
    for _, doses in schedule.groupby("antigen__code"):
        previous = pd.Series(pd.NaT, index=kids.index, dtype="datetime64[ns]")
        for dose in doses.itertuples():
            code = dose.dose_code
            due = kids["date_of_birth"] + pd.to_timedelta(dose.recommended_age_days, unit="D")
            earliest = previous + pd.to_timedelta(dose.min_interval_days, unit="D")
            due = due.where(earliest.isna() | (earliest <= due), earliest)
            closes[code] = kids["date_of_birth"] + pd.to_timedelta(dose.max_age_days, unit="D")
            missing = given[code].isna()
            still_open = now <= closes[code]
            overdue[code] = missing & still_open & (now > due + pd.to_timedelta(OVERDUE_AFTER_DAYS, unit="D"))
            previous = given[code].where(~missing, previous)
    rows = []
    for child_id in overdue.index[overdue.any(axis=1)]:
        codes = [c for c in overdue.columns if overdue.at[child_id, c]]
        nearest = min((closes.at[child_id, c] - now).days for c in codes)
        rows.append((-len(codes), nearest, kids.at[child_id, "system_id"], sorted(codes)))
    return [(system_id, codes) for _, _, system_id, codes in sorted(rows)]
