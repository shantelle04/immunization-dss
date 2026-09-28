"""Checks that a simulator run is internally consistent and matches its calibration targets.

Hard checks fail the run. Informational tables are reported for the thesis (Chapter 5.3).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import SimConfig
from .outputs import sha256


@dataclass
class Check:
    check_id: str
    description: str
    passed: bool
    detail: str


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    tables: dict[str, list[dict]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def add(self, check_id: str, description: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(check_id, description, bool(passed), detail))


def _load(run_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for group in ("app", "truth"):
        for path in sorted((run_dir / group).glob("*.csv")):
            frames[path.stem] = pd.read_csv(path, keep_default_na=False, low_memory=False)
    return frames


def coverage_table(cfg: SimConfig, events: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """KDHS-style coverage at the as-of date: children 12 to 23 months (MR2: 24 to 35 months)."""
    as_of = cfg.as_of_date.toordinal()
    dob = truth.date_of_birth.map(lambda s: dt.date.fromisoformat(s).toordinal())
    age = as_of - dob
    ev = events.assign(given=events.given_on.map(lambda s: dt.date.fromisoformat(s).toordinal()))
    ev = ev[ev.given < as_of]
    targets = cfg.section("calibration")["targets"]
    rows = []
    for dose, rule in cfg.dose_rules.items():
        lo, hi = (730, 1095) if rule.target_key == "mr2" else (365, 730)
        cohort = truth.child_id[(age >= lo) & (age < hi)]
        got = ev[(ev.dose_code == dose) & ev.child_id.isin(cohort)].child_id.nunique()
        sim = got / len(cohort) if len(cohort) else float("nan")
        rows.append(
            {
                "indicator": rule.target_key,
                "cohort_size": len(cohort),
                "simulated_pct": round(100 * sim, 1),
                "kdhs_2022_pct": round(100 * targets.get(rule.target_key, float("nan")), 1),
            }
        )
    cohort = truth.child_id[(age >= 365) & (age < 730)]
    zero = 1 - ev[ev.child_id.isin(cohort)].child_id.nunique() / max(len(cohort), 1)
    rows.append(
        {
            "indicator": "zero_dose",
            "cohort_size": len(cohort),
            "simulated_pct": round(100 * zero, 1),
            "kdhs_2022_pct": round(100 * targets["zero_dose"], 1),
        }
    )
    table = pd.DataFrame(rows)
    table["difference_pp"] = (table.simulated_pct - table.kdhs_2022_pct).round(1)
    return table


def validate_run(cfg: SimConfig, run_dir: Path) -> Report:
    report = Report()
    f = _load(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())

    bad_hash = [p for p, meta in manifest["files"].items() if sha256(run_dir / p) != meta["sha256"]]
    report.add(
        "V-01",
        "Every file matches its manifest hash",
        not bad_hash,
        f"mismatched: {bad_hash}" if bad_hash else f"{len(manifest['files'])} files verified",
    )

    w = f["weekly_stock"]
    flow = w.opening_doses + w.receipts_doses - w.administered_doses - w.wastage_doses - w.loss_doses
    broken = int((flow != w.closing_doses).sum())
    report.add(
        "V-02",
        "Stock conservation: opening + receipts - administered - wastage - losses = closing",
        broken == 0,
        f"{broken} of {len(w)} facility-antigen-weeks violate it",
    )
    negative = int((w[["opening_doses", "closing_doses"]] < 0).to_numpy().sum())
    report.add("V-03", "Stock never negative", negative == 0, f"{negative} negative balances")

    tx = f["stock_transactions"]
    ledger = tx.groupby(["facility_code", "antigen_code"]).quantity_doses.sum()
    last_week = w.week_start.max()
    closing = w[w.week_start == last_week].set_index(["facility_code", "antigen_code"]).closing_doses
    diff = (ledger - closing).abs()
    report.add(
        "V-04",
        "Transaction ledger sums to the final closing balance",
        bool((diff == 0).all()),
        f"max difference {int(diff.max())} doses",
    )

    ev = f["immunization_events"]
    ch = f["children"].set_index("child_id")
    rules = f["schedule"].set_index("dose_code")
    dob = ev.child_id.map(ch.date_of_birth).map(lambda s: dt.date.fromisoformat(s).toordinal())
    given = ev.given_on.map(lambda s: dt.date.fromisoformat(s).toordinal())
    age = given - dob
    too_young = int((age < ev.dose_code.map(rules.min_age_days)).sum())
    too_old = int((age > ev.dose_code.map(rules.max_age_days)).sum())
    report.add(
        "V-05",
        "No dose before its minimum age or after its maximum age",
        too_young + too_old == 0,
        f"{too_young} too young, {too_old} too old",
    )
    ordered = ev.assign(given=given).sort_values(["child_id", "antigen_code", "given"])
    gap = ordered.groupby(["child_id", "antigen_code"]).given.diff()
    min_int = ordered.dose_code.map(rules.min_interval_days)
    interval_bad = int(((gap < min_int) & gap.notna()).sum())
    report.add(
        "V-06",
        "Minimum interval between doses of the same antigen respected",
        interval_bad == 0,
        f"{interval_bad} violations",
    )
    dups = int(ev.duplicated(["child_id", "dose_code"]).sum())
    report.add("V-07", "No child receives the same dose twice", dups == 0, f"{dups} duplicates")
    series_ok = ordered.groupby(["child_id", "antigen_code"]).dose_number.apply(
        lambda s: s.is_monotonic_increasing
    )
    report.add(
        "V-08",
        "Doses of a series are given in order",
        bool(series_ok.all()),
        f"{int((~series_ok).sum())} out-of-order series",
    )
    registered_only = ~ev.child_id.isin(ch.index)
    report.add(
        "V-09",
        "Every event belongs to a registered child",
        not registered_only.any(),
        f"{int(registered_only.sum())} orphan events",
    )

    cov = coverage_table(cfg, ev, f["children_truth"])
    tol = cfg.section("calibration")["tolerance_pp"]
    worst = cov.difference_pp.abs().max()
    report.add(
        "V-10",
        f"Coverage within {tol} points of KDHS 2022 Table 11 for every antigen",
        worst <= tol,
        f"largest difference {worst} points ({cov.loc[cov.difference_pp.abs().idxmax(), 'indicator']})",
    )
    report.tables["coverage_vs_kdhs2022"] = cov.to_dict("records")

    truth = f["children_truth"]
    as_of = cfg.as_of_date.toordinal()
    t_age = as_of - truth.date_of_birth.map(lambda s: dt.date.fromisoformat(s).toordinal())
    cohort = truth[(t_age >= 365) & (t_age < 730)]
    p3 = set(ev[(ev.dose_code == "PENTA-3") & (given < as_of)].child_id)
    targets = cfg.section("calibration")["penta3_by_group"]
    sub = []
    for group, values in targets.items():
        for cat, kdhs in values.items():
            members = cohort[cohort[group].astype(str) == str(cat)]
            sim = members.child_id.isin(p3).mean() if len(members) else float("nan")
            sub.append(
                {
                    "group": group,
                    "category": str(cat),
                    "n": len(members),
                    "simulated_penta3_pct": round(100 * sim, 1),
                    "kdhs_2022_pct": round(100 * kdhs, 1),
                }
            )
    report.tables["penta3_by_group"] = sub

    delay = []
    rules_age = rules.recommended_age_days
    for dose in ("BCG-1", "PENTA-1", "PENTA-3", "MR-1"):
        d = age[ev.dose_code == dose] - rules_age[dose]
        if len(d):
            delay.append(
                {
                    "dose": dose,
                    "median_days_after_recommended_age": float(np.median(d)),
                    "share_within_28_days_pct": round(100 * float((d <= 28).mean()), 1),
                }
            )
    report.tables["timeliness"] = delay

    stock_weeks = w[w.week_start >= cfg.start_date.isoformat()]
    so = (
        stock_weeks.groupby("antigen_code")
        .agg(
            stockout_weeks=("stockout", "sum"),
            unmet_doses=("unmet_doses", "sum"),
            administered=("administered_doses", "sum"),
            wasted=("wastage_doses", "sum"),
            lost=("loss_doses", "sum"),
        )
        .reset_index()
    )
    so["wastage_rate_pct"] = (100 * so.wasted / (so.administered + so.wasted)).round(1)
    # WHO/V&B/03.18 Rev.1: wastage = (doses supplied - doses administered) / doses supplied, so unopened
    # losses count too. Comparable with the WHO indicative rates; wastage_rate_pct is opened-vial only.
    so["wastage_rate_who_pct"] = (
        100 * (so.wasted + so.lost) / (so.administered + so.wasted + so.lost)
    ).round(1)
    report.tables["stock_summary"] = so.to_dict("records")
    report.add(
        "V-11",
        "Stock-outs occur (the alert evaluation needs positive cases)",
        int(so.stockout_weeks.sum()) > 0,
        f"{int(so.stockout_weeks.sum())} stock-out facility-antigen-weeks",
    )
    return report


def write_report(report: Report, run_dir: Path) -> None:
    payload = {
        "passed": report.passed,
        "checks": [c.__dict__ for c in report.checks],
        "tables": report.tables,
    }
    (run_dir / "validation_report.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    lines = [
        f"# Validation report: {run_dir.name}",
        "",
        f"Overall: {'PASS' if report.passed else 'FAIL'}",
        "",
        "| Check | Description | Result | Detail |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {c.check_id} | {c.description} | {'PASS' if c.passed else 'FAIL'} | {c.detail} |"
        for c in report.checks
    ]
    for name, rows in report.tables.items():
        if not rows:
            continue
        cols = list(rows[0])
        lines += ["", f"## {name}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    (run_dir / "validation_report.md").write_text("\n".join(lines) + "\n")
