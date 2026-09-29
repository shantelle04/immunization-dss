"""Stages 7 and 8 (doc 12): weekly training series from the stock ledger, cleaning rules T-01 to T-03.

Input is only what a clinic system records (app/stock_transactions.csv or the same ledger from the database);
truth/ is never read here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pandas as pd

SERIES_COLUMNS = ["facility_code", "antigen_code", "week_start", "issued", "stockout_flag"]


def _monday(d: pd.Series) -> pd.Series:
    return d - pd.to_timedelta(d.dt.weekday, unit="D")


def build_weekly_series(ledger: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    """One row per facility, antigen and week (Monday) in [start, end).

    T-01: a week with no issues is 0, not missing.
    T-02: only weeks inside the stock window [start, end).
    T-03: stockout_flag marks weeks in which the ledger balance reached zero or below on any day; issues in
          those weeks understate demand (censored), which the evaluation reports separately.
    """
    tx = ledger.copy()
    tx["date"] = pd.to_datetime(tx["date"])
    tx["quantity_doses"] = tx["quantity_doses"].astype(int)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    weeks = pd.date_range(start_ts, pd.Timestamp(end - dt.timedelta(days=1)), freq="W-MON")
    series_keys = tx[["facility_code", "antigen_code"]].drop_duplicates()

    issues = tx[(tx["kind"] == "issue") & (tx["date"] >= start_ts) & (tx["date"] < end_ts)].copy()
    issues["week_start"] = _monday(issues["date"])
    issued = (
        issues.groupby(["facility_code", "antigen_code", "week_start"])["quantity_doses"]
        .sum()
        .mul(-1)
        .rename("issued")
    )

    daily = tx.groupby(["facility_code", "antigen_code", "date"])["quantity_doses"].sum().sort_index()
    balance = daily.groupby(level=[0, 1]).cumsum().rename("balance").reset_index()
    balance = balance[(balance["date"] >= start_ts) & (balance["date"] < end_ts)]
    balance["week_start"] = _monday(balance["date"])
    out_weeks = balance.loc[
        balance["balance"] <= 0, ["facility_code", "antigen_code", "week_start"]
    ].drop_duplicates()
    out_weeks["stockout_flag"] = True

    grid = series_keys.merge(pd.DataFrame({"week_start": weeks}), how="cross")
    frame = grid.merge(issued.reset_index(), how="left", on=["facility_code", "antigen_code", "week_start"])
    frame = frame.merge(out_weeks, how="left", on=["facility_code", "antigen_code", "week_start"])
    frame["issued"] = frame["issued"].fillna(0).astype(int)
    frame["stockout_flag"] = frame["stockout_flag"].eq(True)
    frame = frame.sort_values(["facility_code", "antigen_code", "week_start"]).reset_index(drop=True)
    return frame[SERIES_COLUMNS]


def write_series(frame: pd.DataFrame, path: Path) -> str:
    """Write the series as CSV and return its SHA-256, which every training manifest cites."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.assign(week_start=frame["week_start"].dt.date.astype(str))
    out.to_csv(path, index=False, lineterminator="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_series(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["week_start"])
    frame["stockout_flag"] = frame["stockout_flag"].astype(bool)
    return frame
