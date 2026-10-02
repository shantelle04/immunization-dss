"""Alert improvement study (D-43): weekly alert decisions, a delivery-history gate and a risk score.

Everything a decision uses comes from the stock ledger before the decision week (what the application
sees). Labels for tuning and training are the ledger's own stock-out flag (T-03), never truth/; truth/ is
read only by `evaluate_weekly`, after the decisions are made.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .alerts import DEFAULT_CYCLE_WEEKS, HORIZON, KEY, USE_WINDOW_WEEKS
from .guard import on_training_host, require_training_host

LATE_AFTER_WEEKS = 1  # a delivery counts as late when it comes more than a week after the cycle
HISTORY_INTERVALS = 12  # delivery intervals used for a facility's late rate
MIN_HISTORY_WEEKS = 64  # first decision week with a year of history plus the use window
TARGET_RECALL = 0.95  # D-07
__all__ = ["on_training_host"]

FEATURES = [
    "weeks_of_stock",
    "cover_weeks",
    "weeks_since_receipt",
    "overdue_weeks",
    "late_rate",
    "recent_stockout_weeks",
    "stockout_weeks_52",
    "delivery_cover",
    "usage_factor",
    "demand_4w_over_stock",
    "out_now",
]


def weekly_origins(n_weeks: int, back: int, until_back: int = 0, horizon: int = HORIZON) -> list[int]:
    """Every week index from `back` weeks before the end to `until_back`, with a full horizon after it."""
    return list(range(n_weeks - back, n_weeks - until_back - horizon + 1))


def weekly_ledger(ledger: pd.DataFrame, weeks: pd.DatetimeIndex) -> dict:
    """Per series: weekly totals of every ledger movement, receipts and outflows, aligned to `weeks`."""
    tx = ledger.assign(date=pd.to_datetime(ledger["date"]))
    tx["quantity_doses"] = tx["quantity_doses"].astype(int)
    tx["week_start"] = tx["date"] - pd.to_timedelta(tx["date"].dt.weekday, unit="D")
    out = {}
    for key, g in tx.groupby(KEY):

        def total(mask, g=g):
            return (
                g[mask].groupby("week_start")["quantity_doses"].sum().reindex(weeks, fill_value=0).to_numpy()
            )

        everything = np.ones(len(g), bool)
        out[key] = {
            "net": total(everything),
            "before": int(g.loc[g["week_start"] < weeks[0], "quantity_doses"].sum()),
            "receipt": total((g["kind"] == "receipt").to_numpy()),
            "issue": -total((g["kind"] == "issue").to_numpy()),
            "waste": -total(g["kind"].isin(["wastage", "loss"]).to_numpy()),
        }
    return out


def late_rate(receipt_weeks: np.ndarray, cycle_weeks: int) -> float:
    """Share of a series' recent delivery intervals that were more than a week longer than the cycle."""
    if len(receipt_weeks) < 2:
        return 0.0
    gaps = np.diff(receipt_weeks)[-HISTORY_INTERVALS:]
    return float((gaps > cycle_weeks + LATE_AFTER_WEEKS).mean())


def features(
    ledger: pd.DataFrame, series: pd.DataFrame, origins: list[int], cycle_weeks: int = DEFAULT_CYCLE_WEEKS
) -> pd.DataFrame:
    """One row per series and decision week: ledger state before that week, and the ledger label after it.

    `label` is whether the ledger's stock-out flag is set in any of the next HORIZON weeks (missing when the
    horizon runs past the data).
    """
    weeks = pd.DatetimeIndex(sorted(series["week_start"].unique()))
    by_series = {k: g.sort_values("week_start") for k, g in series.groupby(KEY)}
    rows = []
    for key, w in weekly_ledger(ledger, weeks).items():
        stock = w["before"] + np.concatenate([[0], np.cumsum(w["net"])])  # stock[o] = balance before week o
        flag = by_series[key]["stockout_flag"].to_numpy(bool)
        issued = by_series[key]["issued"].to_numpy(float)
        receipt_idx = np.flatnonzero(w["receipt"] > 0)
        for o in origins:
            past = slice(max(0, o - USE_WINDOW_WEEKS), o)
            issues, waste = w["issue"][past].sum(), w["waste"][past].sum()
            weekly_use = (issues + waste) / USE_WINDOW_WEEKS
            factor = max(1.0, (issues + waste) / issues) if issues > 0 else 1.0
            seen = receipt_idx[receipt_idx < o]
            since = int(o - seen[-1]) if len(seen) else cycle_weeks + HORIZON
            demand = issued[max(0, o - 4) : o].mean() * factor * HORIZON if o else 0.0
            # How many cycles of use the last three deliveries covered: under 1 means chronic short supply.
            recent = w["receipt"][seen[-3:]].mean() if len(seen) else 0.0
            cover = min(5.0, recent / (weekly_use * cycle_weeks)) if weekly_use > 0 else 5.0
            future = flag[o : o + HORIZON]
            rows.append(
                {
                    "facility_code": key[0],
                    "antigen_code": key[1],
                    "origin": o,
                    "origin_week": weeks[o] if o < len(weeks) else weeks[-1] + pd.DateOffset(weeks=1),
                    "stock_doses": int(stock[o]),
                    "weeks_of_stock": min(26.0, stock[o] / weekly_use) if weekly_use > 0 else 26.0,
                    "cover_weeks": HORIZON if since >= cycle_weeks else max(1, cycle_weeks - since),
                    "weeks_since_receipt": since,
                    "overdue_weeks": max(0, since - cycle_weeks),
                    "late_rate": late_rate(seen, cycle_weeks),
                    "recent_stockout_weeks": int(flag[past].sum()),
                    "stockout_weeks_52": int(flag[max(0, o - 52) : o].sum()),
                    "delivery_cover": cover,
                    "usage_factor": factor,
                    "demand_4w_over_stock": min(20.0, demand / max(stock[o], 1)),
                    "out_now": float(stock[o] <= 0),
                    "label": float(future.any()) if len(future) == HORIZON else np.nan,
                }
            )
    return pd.DataFrame(rows)


def evaluate_weekly(decisions: pd.DataFrame, truth: pd.DataFrame, flag: str = "alert") -> dict:
    """Score weekly decisions against truth/weekly_stock.csv (evaluation only).

    A true stock-out week w counts as caught when a decision in weeks w-3 .. w flagged the series, and as
    caught early when a decision in weeks w-3 .. w-1 did (at least one week of warning). An onset is the
    first week of a stock-out episode. Precision: flagged decisions followed by a true stock-out week in
    their 4 weeks / all flagged decisions. Base rate: the share of all decisions followed by a stock-out,
    which is the precision of flagging everything; lift = precision / base rate. Stock-out weeks in the
    first decision week are not counted,
    because no earlier decision exists for them.
    """
    t = truth.assign(week_start=pd.to_datetime(truth["week_start"]))
    t["stockout"] = t["stockout"].astype(str).str.lower().eq("true")
    first, last = decisions["origin_week"].min(), decisions["origin_week"].max()
    weeks = pd.date_range(first, last + pd.DateOffset(weeks=HORIZON - 1), freq="W-MON")
    index = {w: i for i, w in enumerate(weeks)}
    n_origins = len(pd.date_range(first, last, freq="W-MON"))
    out_weeks = caught = early = onsets = onsets_early = flagged = flagged_hit = at_risk = 0
    truth_by = {k: g.set_index("week_start")["stockout"] for k, g in t.groupby(KEY)}
    for key, d in decisions.groupby(KEY):
        alert = np.zeros(n_origins, bool)
        for row in d.itertuples():
            alert[index[row.origin_week]] = bool(getattr(row, flag))
        full = truth_by[key]
        actual = full.reindex(weeks).fillna(False).to_numpy(bool)
        before = bool(full.get(first - pd.DateOffset(weeks=1), False))
        for w in np.flatnonzero(actual)[np.flatnonzero(actual) > 0]:  # week 0 has no earlier decision
            window = alert[max(0, w - HORIZON + 1) : min(w, n_origins - 1) + 1]
            prior = alert[max(0, w - HORIZON + 1) : min(w, n_origins)]
            onset = not (actual[w - 1] if w else before)
            out_weeks += 1
            caught += window.any()
            early += prior.any()
            onsets += onset
            onsets_early += onset and prior.any()
        for o in range(n_origins):
            hit = actual[o : o + HORIZON].any()
            at_risk += hit
            flagged += alert[o]
            flagged_hit += alert[o] and hit
    recall = caught / out_weeks if out_weeks else float("nan")
    precision = flagged_hit / flagged if flagged else float("nan")
    return {
        "decisions": int(len(decisions)),
        "flagged": int(flagged),
        "flagged_share": round(flagged / len(decisions), 4),
        "true_stockout_weeks": int(out_weeks),
        "recall": round(recall, 4),
        "early_recall": round(early / out_weeks, 4) if out_weeks else None,
        "onsets": int(onsets),
        "onset_early_recall": round(onsets_early / onsets, 4) if onsets else None,
        "precision_stockout_only": round(precision, 4),
        "base_rate": round(at_risk / len(decisions), 4),
        "lift": round(precision / (at_risk / len(decisions)), 2) if at_risk else None,
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall > 0 else None,
    }


def ledger_recall(frame: pd.DataFrame, flagged: pd.Series) -> float:
    """Share of decisions whose ledger label is positive that were flagged (tuning only, no truth/)."""
    positive = frame["label"] == 1
    return float(flagged[positive].mean()) if positive.any() else float("nan")


def pick_late_rate_gate(frame: pd.DataFrame, base_alert: pd.Series, late_run_out: pd.Series) -> float:
    """Highest late-rate threshold at which alert-or-gated-warning reaches the target recall on the ledger
    labels of the tuning weeks; 0.0 (no gate) if none does."""
    for gate in sorted(frame["late_rate"].unique(), reverse=True):
        flagged = base_alert | (late_run_out & (frame["late_rate"] >= gate))
        if ledger_recall(frame, flagged) >= TARGET_RECALL:
            return float(gate)
    return 0.0


def fit_risk_score(train: pd.DataFrame, tune: pd.DataFrame, seed: int) -> tuple[object, float, dict]:
    """Logistic regression on ledger features, with the threshold set on later weeks (Colab only, D-14).

    The threshold is the highest probability cut at which recall on the tuning weeks' ledger labels is at
    least the target, so precision is as high as the target allows.
    """
    require_training_host("Fitting the stock-out risk score")
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    train, tune = train.dropna(subset=["label"]), tune.dropna(subset=["label"])
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed))
    model.fit(train[FEATURES], train["label"].astype(int))
    scores = model.predict_proba(tune[FEATURES])[:, 1]
    positives = np.sort(scores[tune["label"].to_numpy() == 1])
    # The cut that keeps TARGET_RECALL of the tuning positives at or above it.
    threshold = float(positives[int(np.floor((1 - TARGET_RECALL) * len(positives)))])
    info = {
        "train_rows": int(len(train)),
        "train_positive_share": round(float(train["label"].mean()), 4),
        "tune_rows": int(len(tune)),
        "threshold": round(threshold, 4),
        "tune_recall_ledger": round(float((scores[tune["label"].to_numpy() == 1] >= threshold).mean()), 4),
        "tune_flagged_share": round(float((scores >= threshold).mean()), 4),
        "coefficients": dict(zip(FEATURES, np.round(model[-1].coef_[0], 4).tolist(), strict=True)),
    }
    return model, threshold, info
