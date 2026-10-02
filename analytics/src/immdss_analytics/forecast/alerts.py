"""Stock-out alert rule (BR-05, doc 05 section 2) and its evaluation against simulator ground truth.

The rule sees only what a clinic system records: the ledger balance, the date of the last receipt, recent
weekly use and the forecast's upper bound. truth/ is read only by `evaluate`, after the alerts are decided.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

HORIZON = 4
USE_WINDOW_WEEKS = 12
DEFAULT_CYCLE_WEEKS = 4
DEFAULT_BUFFER = 0.25  # D-33
DEFAULT_GRACE_WEEKS = 1  # D-42: a delivery up to one week late (ASSUMPTION)
KEY = ["facility_code", "antigen_code"]


@dataclass(frozen=True)
class Breach:
    week_ahead: int
    projected_doses: float
    safety_minimum: float


def usage_factor(issued: float, wasted: float) -> float:
    """Doses leaving stock per dose administered, from the ledger: (issues + wastage and losses) / issues.

    The forecast predicts doses administered; a multi-dose vial without an open-vial policy is discarded at
    the end of the session, so stock falls faster than doses are given. At least 1; 1 when nothing was issued.
    """
    return max(1.0, (issued + wasted) / issued) if issued > 0 else 1.0


def weeks_to_replenishment(last_receipt: dt.date | None, cycle_weeks: int, on: dt.date, horizon: int) -> int:
    """Whole weeks from `on` to the expected next receipt (last receipt plus one cycle).

    No receipt on record, or an expected date already passed (a late delivery), gives the full horizon: the
    rule then assumes nothing arrives in the weeks it can see.
    """
    if last_receipt is None:
        return horizon
    expected = last_receipt + dt.timedelta(weeks=cycle_weeks)
    if expected <= on:
        return horizon
    return max(1, -(-(expected - on).days // 7))


def projection(
    stock: float, upper: list[float], weekly_use: float, cover_weeks: int, buffer: float
) -> list[dict]:
    """Projected stock and safety minimum at the end of each week ahead, up to the next replenishment.

    `upper` is the forecast's upper bound in doses leaving stock (administered doses x usage factor).
    Projected stock after k weeks = stock - cumulative upper-bound use (no receipt is assumed before the
    replenishment). Safety minimum after k weeks = average weekly use x weeks still to cover x (1 + buffer).
    """
    rows, used = [], 0.0
    for k in range(1, min(len(upper), cover_weeks) + 1):
        used += float(upper[k - 1])
        rows.append(
            {
                "week_ahead": k,
                "projected_doses": round(stock - used, 2),
                "safety_minimum": round(weekly_use * (cover_weeks - k) * (1 + buffer), 2),
            }
        )
    return rows


def first_breach(
    stock: float, upper: list[float], weekly_use: float, cover_weeks: int, buffer: float
) -> Breach | None:
    """The first week ahead in which projected stock falls below the safety minimum, if any."""
    for row in projection(stock, upper, weekly_use, cover_weeks, buffer):
        if row["projected_doses"] < row["safety_minimum"]:
            return Breach(row["week_ahead"], row["projected_doses"], row["safety_minimum"])
    return None


def run_out_if_delivery_late(
    stock: float, upper: list[float], cover_weeks: int, grace_weeks: int
) -> Breach | None:
    """Late-delivery check (D-42): would stock reach zero if the expected delivery came up to `grace_weeks`
    late? Looks only at the weeks just after the expected delivery, which the main rule does not cover.

    Kept for the evaluation: on the evidence run it flags about 96% of decisions even with a one-week grace,
    so it does not separate risky series from safe ones and is not used as an alert.
    """
    used = 0.0
    for k, use in enumerate(upper[: cover_weeks + grace_weeks], start=1):
        used += float(use)
        if k > cover_weeks and stock - used < 0:
            return Breach(k, round(stock - used, 2), 0.0)
    return None


@dataclass(frozen=True)
class SeriesState:
    stock_doses: int
    last_receipt: dt.date | None
    weekly_use: float
    usage_factor: float


def series_state(transactions: pd.DataFrame, on: pd.Timestamp) -> SeriesState:
    """What the ledger of one facility and antigen says before `on` (columns date, kind, quantity_doses)."""
    before = transactions[transactions["date"] < on]
    receipts = before.loc[before["kind"] == "receipt", "date"]
    recent = before[before["date"] >= on - pd.DateOffset(weeks=USE_WINDOW_WEEKS)]
    issued = -int(recent.loc[recent["kind"] == "issue", "quantity_doses"].sum())
    wasted = -int(recent.loc[recent["kind"].isin(["wastage", "loss"]), "quantity_doses"].sum())
    return SeriesState(
        stock_doses=int(before["quantity_doses"].sum()),
        last_receipt=receipts.max().date() if len(receipts) else None,
        weekly_use=(issued + wasted) / USE_WINDOW_WEEKS,
        usage_factor=usage_factor(issued, wasted),
    )


def breach_for(
    state: SeriesState, hi80: list[float], on: dt.date, cycle_weeks: int, buffer: float
) -> tuple[int, Breach | None]:
    """Cover weeks and the first breach for one series, from its ledger state and forecast upper bound."""
    cover = weeks_to_replenishment(state.last_receipt, cycle_weeks, on, HORIZON)
    upper = [u * state.usage_factor for u in hi80]
    return cover, first_breach(state.stock_doses, upper, state.weekly_use, cover, buffer)


def decide(
    ledger: pd.DataFrame,
    forecasts: pd.DataFrame,
    selection: pd.DataFrame,
    cycle_weeks: int = DEFAULT_CYCLE_WEEKS,
    buffer: float = DEFAULT_BUFFER,
    grace_weeks: int = DEFAULT_GRACE_WEEKS,
) -> pd.DataFrame:
    """One row per backtest origin and series: the alert decision from data before the origin only."""
    tx = ledger.assign(date=pd.to_datetime(ledger["date"]))
    tx["quantity_doses"] = tx["quantity_doses"].astype(int)
    chosen = {(r.facility_code, r.antigen_code): r.model for r in selection.itertuples()}
    fc = forecasts.assign(
        week_start=pd.to_datetime(forecasts["week_start"]),
        origin_week=pd.to_datetime(forecasts["origin_week"]),
    )
    tx_by_series = {k: g for k, g in tx.groupby(KEY)}
    rows = []
    for (fac, ant, origin), g in fc.groupby([*KEY, "origin_week"], sort=True):
        g = g[g["model"] == chosen[(fac, ant)]].sort_values("h")
        state = series_state(tx_by_series[(fac, ant)], origin)
        hi80 = list(g["hi80"])
        cover, breach = breach_for(state, hi80, origin.date(), cycle_weeks, buffer)
        # Evaluated only (D-42): the application does not raise this warning.
        late = [u * state.usage_factor for u in hi80]
        warning = None if breach else run_out_if_delivery_late(state.stock_doses, late, cover, grace_weeks)
        rows.append(
            {
                "facility_code": fac,
                "antigen_code": ant,
                "origin_week": origin,
                "model": chosen[(fac, ant)],
                "stock_doses": state.stock_doses,
                "weekly_use": round(state.weekly_use, 2),
                "usage_factor": round(state.usage_factor, 2),
                "cover_weeks": cover,
                "alert": breach is not None,
                "breach_week_ahead": breach.week_ahead if breach else np.nan,
                "warning": warning is not None,
                "warning_week_ahead": warning.week_ahead if warning else np.nan,
            }
        )
    return pd.DataFrame(rows)


def evaluate(
    decisions: pd.DataFrame, truth: pd.DataFrame, buffer: float = DEFAULT_BUFFER
) -> tuple[pd.DataFrame, dict]:
    """Score alert decisions against truth/weekly_stock.csv (evaluation only; doc 05 section 2).

    Recall: true stock-out weeks in the 4 weeks after an origin that had an alert / all true stock-out weeks.
    Precision: alerts followed within 4 weeks by a true stock-out week or a true below-minimum week / all
    alerts (strict precision counts stock-out weeks only). Lead time: weeks from the alert to the first true
    stock-out week (1 = the week starting at the origin).
    """
    t = truth.assign(week_start=pd.to_datetime(truth["week_start"]))
    t["stockout"] = t["stockout"].astype(str).str.lower().eq("true")
    by_series = {k: g.set_index("week_start") for k, g in t.groupby(KEY)}
    scored = []
    for d in decisions.itertuples():
        weeks = pd.date_range(d.origin_week, periods=HORIZON, freq="W-MON")
        window = by_series[(d.facility_code, d.antigen_code)].reindex(weeks)
        out = window["stockout"].fillna(False).to_numpy(bool)
        minimum = d.weekly_use * np.clip(d.cover_weeks - np.arange(1, HORIZON + 1), 0, None) * (1 + buffer)
        below = (window["closing_doses"].to_numpy(float) < minimum) & (
            np.arange(1, HORIZON + 1) <= d.cover_weeks
        )
        scored.append(
            {
                **d._asdict(),
                "true_stockout_weeks": int(out.sum()),
                "true_below_minimum": bool(below.any()),
                "first_stockout_week_ahead": int(np.argmax(out)) + 1 if out.any() else np.nan,
            }
        )
    frame = pd.DataFrame(scored).drop(columns="Index")
    alerts = frame[frame["alert"]]
    stockout_weeks = int(frame["true_stockout_weeks"].sum())
    caught_weeks = int(alerts["true_stockout_weeks"].sum())
    hit = alerts["true_stockout_weeks"] > 0
    useful = hit | alerts["true_below_minimum"]
    recall = caught_weeks / stockout_weeks if stockout_weeks else float("nan")
    precision = float(useful.mean()) if len(alerts) else float("nan")
    strict = float(hit.mean()) if len(alerts) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else float("nan")
    lead = alerts.loc[hit, "first_stockout_week_ahead"]
    episodes = frame[frame["true_stockout_weeks"] > 0]
    summary = {
        "decisions": int(len(frame)),
        "alerts": int(len(alerts)),
        "true_stockout_weeks": stockout_weeks,
        "true_stockout_weeks_alerted": caught_weeks,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "precision_stockout_only": round(strict, 4),
        "f1": round(f1, 4),
        "origins_with_stockout": int(len(episodes)),
        "origins_with_stockout_alerted": int(episodes["alert"].sum()),
        "mean_lead_time_weeks": round(float(lead.mean()), 2) if len(lead) else None,
        "buffer": buffer,
    }
    return frame, summary
