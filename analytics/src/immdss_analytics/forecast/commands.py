"""The `immdss build-series`, `backtest`, `train-final` and `evaluate-alerts` commands (doc 12)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import alert_study, alerts
from . import backtest as bt
from .series import build_weekly_series, read_series, write_series

SERIES_FILE = "weekly_issues.csv"
SENSITIVITY_BUFFERS = (0.0, 0.1, 0.25, 0.5)
GRACE_WEEKS = (1, 2, 3)
STUDY_KEY = ["facility_code", "antigen_code", "origin_week"]
WITH_WARNINGS_KEYS = (
    "alerts",
    "true_stockout_weeks_alerted",
    "recall",
    "precision",
    "precision_stockout_only",
    "f1",
    "mean_lead_time_weeks",
)


def _run_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text())


def build_series(run_dir: Path, out_root: Path) -> Path:
    manifest = _run_manifest(run_dir)
    if not json.loads((run_dir / "validation_report.json").read_text())["passed"]:
        raise SystemExit(
            "This run did not pass validate-sim; training series are built only from validated runs."
        )
    window = manifest["window"]
    ledger = pd.read_csv(run_dir / "app" / "stock_transactions.csv", keep_default_na=False)
    frame = build_weekly_series(
        ledger, pd.Timestamp(window["stock_from"]).date(), pd.Timestamp(window["end"]).date()
    )
    out = out_root / manifest["run_id"]
    sha = write_series(frame, out / SERIES_FILE)
    summary = {
        "run_id": manifest["run_id"],
        "source": "app/stock_transactions.csv (issues only; truth/ not read)",
        "series": int(frame.groupby(["facility_code", "antigen_code"]).ngroups),
        "weeks": int(frame["week_start"].nunique()),
        "first_week": str(frame["week_start"].min().date()),
        "last_week": str(frame["week_start"].max().date()),
        "stockout_flagged_weeks": int(frame["stockout_flag"].sum()),
        "zero_issue_weeks": int((frame["issued"] == 0).sum()),
        "sha256": sha,
    }
    (out / "series_manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return out / SERIES_FILE


def run_backtests(run_dir: Path, series_path: Path, model_names: list[str], seed: int, out: Path) -> Path:
    series = read_series(series_path)
    series_sha = json.loads((series_path.parent / "series_manifest.json").read_text())["sha256"]
    out.mkdir(parents=True, exist_ok=True)
    forecasts = bt.run_backtest(series, model_names, seed)
    metrics = bt.score(forecasts, series)
    overall, per_vaccine, selection = bt.compare(metrics)
    forecasts.to_csv(out / "forecasts.csv", index=False)
    metrics.to_csv(out / "metrics.csv", index=False)
    overall.to_csv(out / "comparison_overall.csv", index=False)
    per_vaccine.to_csv(out / "comparison_by_vaccine.csv", index=False)
    selection.to_csv(out / "selection.csv", index=False)
    # Evaluation only: forecasts are compared with true demand after they are made; no model saw truth/.
    truth_file = run_dir / "truth" / "weekly_stock.csv"
    if truth_file.exists():
        bt.truth_bias(forecasts, pd.read_csv(truth_file)).to_csv(out / "truth_bias.csv", index=False)
    weeks = int(series["week_start"].nunique())
    info = bt.manifest(series_sha, _run_manifest(run_dir)["run_id"], model_names, seed, Path.cwd(), weeks)
    info["overall"] = overall.to_dict("records")
    (out / "manifest.json").write_text(json.dumps(info, indent=2, default=str) + "\n")
    print(overall.to_string(index=False))
    return out


def train_final(series_path: Path, results: Path, seed: int) -> Path:
    series = read_series(series_path)
    selection = pd.read_csv(results / "selection.csv")
    final = bt.train_final(series, selection, seed, results)
    final.to_csv(results / "final_forecasts.csv", index=False)
    print(final.groupby("model").size().rename("series_weeks").to_string())
    return results / "final_forecasts.csv"


def evaluate_alerts(run_dir: Path, results: Path) -> Path:
    """Alert decisions at every backtest origin from app/ data, then scored against truth/ (evaluation)."""
    ledger = pd.read_csv(run_dir / "app" / "stock_transactions.csv", keep_default_na=False)
    forecasts = pd.read_csv(results / "forecasts.csv")
    selection = pd.read_csv(results / "selection.csv")
    decisions = alerts.decide(ledger, forecasts, selection)
    truth = pd.read_csv(run_dir / "truth" / "weekly_stock.csv")
    scored, summary = alerts.evaluate(decisions, truth)
    by_vaccine = {}
    for antigen, part in scored.groupby("antigen_code"):
        raised = part[part["alert"]]
        weeks = int(part["true_stockout_weeks"].sum())
        by_vaccine[antigen] = {
            "alerts": int(len(raised)),
            "true_stockout_weeks": weeks,
            "recall": round(int(raised["true_stockout_weeks"].sum()) / weeks, 4) if weeks else None,
        }
    summary["by_vaccine"] = by_vaccine
    # Sensitivity only: how the trade-off moves with the safety buffer. The reported result uses D-33.
    summary["sensitivity"] = []
    for buffer in SENSITIVITY_BUFFERS:
        _, at = alerts.evaluate(alerts.decide(ledger, forecasts, selection, buffer=buffer), truth, buffer)
        summary["sensitivity"].append({k: at[k] for k in ("buffer", "alerts", "recall", "precision", "f1")})
    # D-42: alerts plus late-delivery warnings, scored the same way; the reported value uses a 1-week grace.
    summary["with_late_delivery_check"] = []
    for grace in GRACE_WEEKS:
        d = alerts.decide(ledger, forecasts, selection, grace_weeks=grace)
        _, at = alerts.evaluate(d.assign(alert=d["alert"] | d["warning"]), truth)
        row = {
            "grace_weeks": grace,
            "warnings": int(d["warning"].sum()),
            "flagged_share": round(at["alerts"] / len(d), 3),
        }
        summary["with_late_delivery_check"].append(row | {k: at[k] for k in WITH_WARNINGS_KEYS})
    summary["models_used"] = selection["model"].value_counts().to_dict()
    summary["run_id"] = _run_manifest(run_dir)["run_id"]
    scored.to_csv(results / "alert_decisions.csv", index=False)
    (results / "alert_metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return results / "alert_metrics.json"


def run_alert_study(run_dir: Path, series_path: Path, results: Path, seed: int, out: Path) -> Path:
    """D-43: weekly alert decisions, the delivery-history gate and the risk score, on the last 24 weeks.

    Tuning (gate, risk threshold) uses the 24 weeks before the test weeks and the ledger's own stock-out
    flag; truth/ is read once, at the end, to score the test weeks.
    """
    series = read_series(series_path)
    ledger = pd.read_csv(run_dir / "app" / "stock_transactions.csv", keep_default_na=False)
    selection = pd.read_csv(results / "selection.csv")
    n = int(series["week_start"].nunique())
    test = alert_study.weekly_origins(n, bt.TEST_WEEKS)
    tune = alert_study.weekly_origins(n, 2 * bt.TEST_WEEKS, bt.TEST_WEEKS)
    only = {
        model: {(r.facility_code, r.antigen_code) for r in part.itertuples()}
        for model, part in selection.groupby("model")
    }
    out.mkdir(parents=True, exist_ok=True)
    cached = out / "weekly_forecasts.csv"
    if cached.exists():
        forecasts = pd.read_csv(cached)
    else:
        forecasts = bt.run_backtest(series, sorted(only), seed, cuts=tune + test, only=only)
        # Saved before anything else runs: these fits take most of the time on Colab.
        forecasts.to_csv(cached, index=False)
    # The rule's own state columns are dropped so the study's features are the same in training and scoring.
    decided = alerts.decide(ledger, forecasts, selection)[[*STUDY_KEY, "model", "alert", "warning"]]
    frame = decided.merge(alert_study.features(ledger, series, tune + test), on=STUDY_KEY)
    is_test = frame["origin"].isin(test)
    tuning, scored = frame[~is_test], frame[is_test].copy()
    gate = alert_study.pick_late_rate_gate(tuning, tuning["alert"], tuning["warning"])
    scored["alert_or_late"] = scored["alert"] | scored["warning"]
    scored["alert_or_gated"] = scored["alert"] | (scored["warning"] & (scored["late_rate"] >= gate))
    methods = {
        "rule, weekly decisions": "alert",
        "rule + late-delivery warning (all facilities)": "alert_or_late",
        "rule + late-delivery warning gated by delivery history": "alert_or_gated",
    }
    info: dict = {"late_rate_gate": gate, "tuning_origins": len(tune), "test_origins": len(test)}
    if alert_study.on_training_host():
        train = alert_study.features(
            ledger, series, list(range(alert_study.MIN_HISTORY_WEEKS, tune[0] - bt.HORIZON + 1))
        )
        model, threshold, info["risk_score"] = alert_study.fit_risk_score(train, tuning, seed)
        scored["risk"] = model.predict_proba(scored[alert_study.FEATURES])[:, 1]
        scored["risk_flag"] = scored["risk"] >= threshold
        scored["risk_or_rule"] = scored["risk_flag"] | scored["alert"]
        methods["risk score"] = "risk_flag"
        methods["risk score or rule"] = "risk_or_rule"
    else:
        info["risk_score"] = "not run: the risk score is fitted on Colab only (D-14)"
    truth = pd.read_csv(run_dir / "truth" / "weekly_stock.csv")
    rows = [
        {"method": name} | alert_study.evaluate_weekly(scored, truth, flag) for name, flag in methods.items()
    ]
    out.mkdir(parents=True, exist_ok=True)
    scored.to_csv(out / "weekly_decisions.csv", index=False)
    pd.DataFrame(rows).to_csv(out / "alert_study.csv", index=False)
    series_sha = json.loads((series_path.parent / "series_manifest.json").read_text())["sha256"]
    manifest = bt.manifest(series_sha, _run_manifest(run_dir)["run_id"], sorted(only), seed, Path.cwd(), n)
    manifest |= info | {"models_used": selection["model"].value_counts().to_dict(), "results": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    print(pd.DataFrame(rows).to_string(index=False))
    print(json.dumps(info, indent=2))
    return out
