"""Fit behaviour parameters so that a stock-unconstrained cohort reproduces the published coverage.

Coverage is measured the way the KDHS measures it: children aged 12 to 23 months at the survey
(24 to 35 months for MR2) who received the dose at any time before the survey.
"""

from __future__ import annotations

import math

import numpy as np

from .behaviour import (
    Params,
    Series,
    draw_plan,
    initial_params,
    offer,
    planned_visit,
    record_given,
)
from .config import SimConfig
from .population import draw_background

SECOND_YEAR_KEYS = {"mr2"}


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def anchors(cfg: SimConfig) -> dict[int, str]:
    """For every contact after birth, the dose with the highest target sets the attendance intercept."""
    targets = cfg.section("calibration")["targets"]
    return {
        c: max(contact.doses, key=lambda d: targets.get(cfg.dose_rules[d].target_key, 0.0))
        for c, contact in enumerate(cfg.contacts)
        if c > 0
    }


def simulate_cohort(
    cfg: SimConfig, params: Params, rng: np.random.Generator, n: int
) -> tuple[dict[str, float], np.ndarray]:
    series = Series.from_config(cfg)
    residences = np.array([f.residence for f in cfg.facilities], dtype=object)
    weights = np.array([f.births_per_week for f in cfg.facilities])
    residence = residences[rng.choice(len(residences), size=n, p=weights / weights.sum())]
    bg = draw_background(cfg, rng, n, residence)
    dob = cfg.as_of_date.toordinal() - 1200 + rng.integers(0, 365, size=n)
    plan = draw_plan(cfg, params, rng, dob, bg["risk"])
    survey_age = rng.integers(365, 730, size=n)
    survey_age_2 = rng.integers(730, 1095, size=n)

    given_age: dict[str, np.ndarray] = {d: np.full(n, 10**6, dtype=np.int64) for d in cfg.dose_rules}
    for i in range(n):
        if not plan.entered[i]:
            continue
        next_number = dict(series.first_number)
        last_date: dict[str, int] = {}
        previous = None
        for c in range(int(plan.first_contact[i]), len(cfg.contacts)):
            if not plan.attend[i, c]:
                break
            visit = planned_visit(cfg, int(dob[i]), c, int(plan.delay[i, c]), previous)
            for dose in offer(cfg, series, params, rng, visit, int(dob[i]), next_number, last_date):
                record_given(series, dose.split("-")[0], dose, visit, next_number, last_date)
                given_age[dose][i] = visit - dob[i]
            previous = visit

    coverage: dict[str, float] = {}
    for dose, rule in cfg.dose_rules.items():
        ages = survey_age_2 if rule.target_key in SECOND_YEAR_KEYS else survey_age
        coverage[rule.target_key] = float(np.mean(given_age[dose] < ages))
    any_dose = np.min(np.stack(list(given_age.values())), axis=0)
    coverage["zero_dose"] = float(np.mean(any_dose >= survey_age))
    return coverage, plan.dropout_after()


def calibrate(cfg: SimConfig, rng: np.random.Generator) -> tuple[Params, dict]:
    cal = cfg.section("calibration")
    targets = cal["targets"]
    n = int(cal.get("cohort_size", 40000))
    iterations = int(cal.get("iterations", 16))
    # Doses in one series are coupled (a missed dose shifts the later ones), so steps are damped.
    damping = float(cal.get("damping", 0.5))
    params = initial_params(cfg)
    anchor = anchors(cfg)
    anchor_doses = set(anchor.values())
    history = []
    coverage: dict[str, float] = {}
    for it in range(iterations):
        coverage, _ = simulate_cohort(cfg, params, np.random.default_rng(rng.integers(2**63)), n)
        error = {k: round(100 * (coverage[k] - targets[k]), 2) for k in targets}
        history.append({"iteration": it, "max_abs_error_pp": max(abs(v) for v in error.values())})
        params.entry += damping * (_logit(1 - targets["zero_dose"]) - _logit(1 - coverage["zero_dose"]))
        for c, dose in anchor.items():
            key = cfg.dose_rules[dose].target_key
            if key in targets:
                params.attend[c] += damping * (_logit(targets[key]) - _logit(coverage[key]))
        for dose, rule in cfg.dose_rules.items():
            key = rule.target_key
            if dose in anchor_doses or key not in targets or coverage[key] <= 0:
                continue
            step = (targets[key] / coverage[key]) ** damping
            params.give_prob[dose] = float(np.clip(params.give_prob[dose] * step, 0.01, 1.0))
    final = {k: round(100 * (coverage[k] - targets[k]), 2) for k in targets}
    report = {"cohort_size": n, "iterations": history, "final_error_pp": final, "params": params.to_dict()}
    return params, report


def refine(cfg: SimConfig, params: Params, coverage_pct: dict[str, float]) -> Params:
    """Second stage: correct for what the stock-free cohort cannot see (stock-outs, session timing).

    `coverage_pct` is the full engine's KDHS-style coverage in percent. Steps are damped for the same
    reason as in `calibrate`: one contact's attendance moves several doses, and stock-outs respond
    non-linearly to how many doses are given, so full steps overshoot and oscillate.
    """
    cal = cfg.section("calibration")
    targets = cal["targets"]
    damping = float(cal.get("engine_damping", 1.0))
    sim = {k: min(max(v / 100.0, 1e-4), 1 - 1e-4) for k, v in coverage_pct.items()}
    anchor = anchors(cfg)
    anchor_doses = set(anchor.values())
    params.entry += damping * (_logit(1 - targets["zero_dose"]) - _logit(1 - sim["zero_dose"]))
    for c, dose in anchor.items():
        key = cfg.dose_rules[dose].target_key
        params.attend[c] += damping * (_logit(targets[key]) - _logit(sim[key]))
    for dose, rule in cfg.dose_rules.items():
        key = rule.target_key
        if dose not in anchor_doses and key in targets:
            step = (targets[key] / sim[key]) ** damping
            params.give_prob[dose] = float(np.clip(params.give_prob[dose] * step, 0.01, 1.0))
    return params
