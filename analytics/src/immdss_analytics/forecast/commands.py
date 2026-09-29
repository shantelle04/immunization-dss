"""The `immdss build-series`, `backtest` and `train-final` commands (doc 12 stages 7 to 12)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import backtest as bt
from .series import build_weekly_series, read_series, write_series

SERIES_FILE = "weekly_issues.csv"


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
