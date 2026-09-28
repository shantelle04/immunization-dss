"""Care-seeking behaviour: who enters care, who returns for each contact, how late, and dose decisions.

Shared by the calibration pass (no stock limits) and the full engine (with stock), so both apply the
same schedule rules.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np

from .config import SimConfig

ABSENT = -1
CLOSED = 99


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class Params:
    """Calibrated behaviour parameters. Intercepts are log-odds; give_prob is per dose."""

    entry: float
    attend: list[float]
    give_prob: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"entry": self.entry, "attend": self.attend, "give_prob": self.give_prob}


def initial_params(cfg: SimConfig) -> Params:
    targets = cfg.section("calibration")["targets"]
    return Params(
        entry=float(np.log((1 - targets["zero_dose"]) / targets["zero_dose"])),
        attend=[3.0] * len(cfg.contacts),
        give_prob={d: 1.0 for d in cfg.dose_rules},
    )


@dataclass
class Series:
    """Dose series per antigen, in order, e.g. OPV: [OPV-0, OPV-1, OPV-2, OPV-3]."""

    antigens: list[str]
    doses: dict[str, list[str]]
    first_number: dict[str, int]

    @classmethod
    def from_config(cls, cfg: SimConfig) -> Series:
        antigens = list(cfg.antigens)
        doses = {
            a: sorted(
                (r.dose for r in cfg.dose_rules.values() if r.antigen == a),
                key=lambda d: cfg.dose_rules[d].number,
            )
            for a in antigens
        }
        first = {a: cfg.dose_rules[doses[a][0]].number for a in antigens}
        return cls(antigens, doses, first)


@dataclass
class Plan:
    """Per-child plan drawn up front: entry, first contact, which contacts are attended, delays."""

    entered: np.ndarray
    first_contact: np.ndarray
    attend: np.ndarray
    delay: np.ndarray

    def dropout_after(self) -> np.ndarray:
        """Index of the last attended contact for children who stop early, else -1."""
        n_contacts = self.attend.shape[1]
        last = np.where(self.attend.any(axis=1), n_contacts - 1 - np.argmax(self.attend[:, ::-1], axis=1), -1)
        return np.where(self.entered & (last < n_contacts - 1), last, -1)


def draw_plan(
    cfg: SimConfig, params: Params, rng: np.random.Generator, dob: np.ndarray, risk: np.ndarray
) -> Plan:
    n, k = len(dob), len(cfg.contacts)
    cal, tim = cfg.section("calibration"), cfg.section("timeliness")
    entered = rng.random(n) < sigmoid(params.entry + risk)
    first = np.where(rng.random(n) < cal["first_contact_at_birth"], 0, 1)
    attend = np.zeros((n, k), dtype=bool)
    attend[np.arange(n), first] = entered
    for c in range(1, k):
        cont = rng.random(n) < sigmoid(params.attend[c] + risk)
        attend[:, c] |= attend[:, c - 1] & cont & (first < c)

    medians = np.array([tim["median_delay_days"][c.name] for c in cfg.contacts], dtype=float)
    z = rng.standard_normal((n, k))
    delay = np.exp(np.log(np.maximum(medians, 0.5)) + tim["sigma"] * z)
    delay *= np.exp(-tim["risk_delay_factor"] * risk)[:, None]
    due = dob[:, None] + np.array([c.age_days for c in cfg.contacts])[None, :]
    months = np.vectorize(lambda o: dt.date.fromordinal(int(o)).month)(due)
    delay *= np.where(np.isin(months, tim["rainy_months"]), tim["rainy_delay_multiplier"], 1.0)
    return Plan(entered, first, attend, np.rint(delay).astype(np.int64))


def planned_visit(cfg: SimConfig, dob: int, contact: int, delay: int, previous_visit: int | None) -> int:
    date = dob + cfg.contacts[contact].age_days + delay
    if previous_visit is not None:
        date = max(date, previous_visit + 28)
    return int(date)


def offer(
    cfg: SimConfig,
    series: Series,
    params: Params,
    rng: np.random.Generator,
    visit_date: int,
    dob: int,
    next_number: dict[str, int],
    last_date: dict[str, int],
) -> list[str]:
    """Doses requested at a visit: every dose that is due (catch-up included), each subject to a missed
    opportunity draw. Mutates next_number when a dose is out of its age window and cannot be caught up.
    """
    requested: list[str] = []
    age = visit_date - dob
    for antigen in series.antigens:
        while True:
            number = next_number[antigen]
            if number == CLOSED:
                break
            dose = f"{antigen}-{number}"
            rule = cfg.dose_rules[dose]
            if age > rule.max_age:
                # A birth dose (number 0) that is too late is skipped; the rest of the series still applies.
                if rule.number == 0:
                    next_number[antigen] = _next_in_series(series, antigen, number)
                    continue
                next_number[antigen] = CLOSED
                break
            last = last_date.get(antigen, ABSENT)
            due = age >= rule.min_age and (last == ABSENT or visit_date - last >= rule.min_interval)
            if due and rng.random() < params.give_prob[dose]:
                requested.append(dose)
            break
    return requested


def _next_in_series(series: Series, antigen: str, number: int) -> int:
    doses = series.doses[antigen]
    numbers = [int(d.split("-")[1]) for d in doses]
    later = [x for x in numbers if x > number]
    return later[0] if later else CLOSED


def record_given(
    series: Series,
    antigen: str,
    dose: str,
    visit_date: int,
    next_number: dict[str, int],
    last_date: dict[str, int],
) -> None:
    number = int(dose.split("-")[1])
    last_date[antigen] = visit_date
    next_number[antigen] = _next_in_series(series, antigen, number)
