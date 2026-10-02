"""Stages 9 to 11 (doc 12): rolling-origin backtest, scoring, comparison, model selection and final training.

Origins: the last TEST_WEEKS are split into blocks of HORIZON weeks. At each origin a model sees only the
weeks before it and forecasts the next HORIZON weeks; test weeks are never part of any fit scored on them.
truth/ is read only by `truth_bias`, after forecasting, to measure bias against true demand.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .guard import require_training_host
from .metrics import coverage, mae, naive_scale, smape
from .models import FITTED, PER_SERIES

HORIZON = 4
TEST_WEEKS = 24
MIN_WEEKS_FOR_GRU = 104  # D-21
KEY = ["facility_code", "antigen_code"]


def origins(n_weeks: int, test_weeks: int = TEST_WEEKS, horizon: int = HORIZON) -> list[int]:
    """Week indices where each test block starts; training for a block uses weeks [0, origin)."""
    return list(range(n_weeks - test_weeks, n_weeks - horizon + 1, horizon))


def _grouped(series: pd.DataFrame) -> dict:
    return {key: g.sort_values("week_start") for key, g in series.groupby(KEY, sort=True)}


def _forecast_all(
    model: str, grouped: dict, cut: int, weeks, seed: int, gru_params=None, save_dir: Path | None = None
) -> dict:
    """Forecasts for every series from weeks [0, cut); a fitted GRU is saved when `save_dir` is given."""
    if model == "gru":
        from .gru import fit_and_forecast

        inputs = {
            k: (g["issued"].to_numpy()[:cut], g["stockout_flag"].to_numpy()[:cut]) for k, g in grouped.items()
        }
        out = fit_and_forecast(inputs, weeks[:cut], HORIZON, seed, gru_params)
        fitted = out.pop("_model")
        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            fitted.save(save_dir / "gru.keras")
        return out
    fn = PER_SERIES[model]
    return {k: fn(g["issued"].to_numpy()[:cut], HORIZON) for k, g in grouped.items()}


def run_backtest(series: pd.DataFrame, models: list[str], seed: int = 42, gru_params=None) -> pd.DataFrame:
    """One row per model, series, origin and forecast week."""
    unknown = set(models) - set(PER_SERIES) - {"gru"}
    if unknown:
        raise ValueError(f"unknown models: {sorted(unknown)}")
    if FITTED & set(models):
        require_training_host("Backtesting " + ", ".join(sorted(FITTED & set(models))))
    weeks = pd.DatetimeIndex(sorted(series["week_start"].unique()))
    grouped = _grouped(series)
    rows = []
    for model in models:
        started = time.perf_counter()
        for origin in origins(len(weeks)):
            test_weeks = weeks[origin : origin + HORIZON]
            assert weeks[:origin].max() < test_weeks.min(), (
                "leakage: a test week is inside the training window"
            )
            for key, fc in _forecast_all(model, grouped, origin, weeks, seed, gru_params).items():
                g = grouped[key]
                actual = g["issued"].to_numpy()[origin : origin + HORIZON]
                flags = g["stockout_flag"].to_numpy()[origin : origin + HORIZON]
                for h in range(HORIZON):
                    rows.append(
                        {
                            "model": model,
                            "facility_code": key[0],
                            "antigen_code": key[1],
                            "origin_week": weeks[origin],
                            "week_start": test_weeks[h],
                            "h": h + 1,
                            "train_weeks": origin,
                            "actual": int(actual[h]),
                            "yhat": round(float(fc.yhat[h]), 3),
                            "lo80": round(float(fc.lo80[h]), 3),
                            "hi80": round(float(fc.hi80[h]), 3),
                            "stockout_flag": bool(flags[h]),
                            "detail": json.dumps(fc.detail, default=str),
                        }
                    )
        print(f"{model}: {time.perf_counter() - started:.1f}s", flush=True)
    return pd.DataFrame(rows)


def score(forecasts: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    """Per model and series: MAE, MASE (mean over origins, denominator from training weeks only), sMAPE,
    80% interval coverage, and MAE on test weeks without a ledger stock-out."""
    grouped = _grouped(series)
    weeks = pd.DatetimeIndex(sorted(series["week_start"].unique()))
    index = {w: i for i, w in enumerate(weeks)}
    rows = []
    for (model, fac, ant, origin), g in forecasts.groupby(["model", *KEY, "origin_week"], sort=True):
        train = grouped[(fac, ant)]["issued"].to_numpy()[: index[pd.Timestamp(origin)]]
        clean = g[~g["stockout_flag"]]
        rows.append(
            {
                "model": model,
                "facility_code": fac,
                "antigen_code": ant,
                "mae": mae(g["actual"], g["yhat"]),
                "mase": mae(g["actual"], g["yhat"]) / naive_scale(train),
                "smape": smape(g["actual"], g["yhat"]),
                "coverage80": coverage(g["actual"], g["lo80"], g["hi80"]),
                "mae_no_stockout": mae(clean["actual"], clean["yhat"]) if len(clean) else np.nan,
                "train_weeks": int(g["train_weeks"].min()),
            }
        )
    per_origin = pd.DataFrame(rows)
    return (
        per_origin.groupby(["model", *KEY])
        .agg(
            mae=("mae", "mean"),
            mase=("mase", "mean"),
            smape=("smape", "mean"),
            coverage80=("coverage80", "mean"),
            mae_no_stockout=("mae_no_stockout", "mean"),
            min_train_weeks=("train_weeks", "min"),
        )
        .reset_index()
        .round(4)
    )


def compare(metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Overall and per-vaccine comparison, and the per-series selection (D-21).

    D-21: the GRU is chosen for a series with at least 104 training weeks when it beats the seasonal naive
    baseline (lower MASE); otherwise SARIMA; if SARIMA was not run, the better baseline.
    """

    def summary(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
        return (
            frame.groupby(by)
            .agg(
                series=("mase", "size"),
                mean_mase=("mase", "mean"),
                median_mase=("mase", "median"),
                share_beating_naive=("mase", lambda s: float((s < 1).mean())),
                mean_mae=("mae", "mean"),
                mean_smape=("smape", "mean"),
                coverage80=("coverage80", "mean"),
            )
            .reset_index()
            .round(4)
        )

    overall = summary(metrics, ["model"]).sort_values("mean_mase").reset_index(drop=True)
    per_vaccine = summary(metrics, ["antigen_code", "model"]).sort_values(["antigen_code", "mean_mase"])
    wide = metrics.set_index([*KEY, "model"])["mase"].unstack("model")
    wide_mae = metrics.set_index([*KEY, "model"])["mae"].unstack("model")
    weeks = metrics.groupby(KEY)["min_train_weeks"].min()
    choices = []
    for key, row in wide.iterrows():
        if row.isna().all():
            # MASE is undefined with less than a season of training weeks; models are then compared on MAE.
            row = wide_mae.loc[key]
        if "gru" in row and weeks[key] >= MIN_WEEKS_FOR_GRU and row["gru"] < row.get("b1", np.inf):
            chosen, reason = "gru", "GRU beats seasonal naive with enough history"
        elif "sarima" in row and np.isfinite(row["sarima"]):
            chosen, reason = "sarima", "fallback: SARIMA"
        else:
            baselines = row[[m for m in ("b1", "b2") if m in row]]
            chosen, reason = str(baselines.idxmin()), "fallback: better baseline"
        choices.append(
            {
                "facility_code": key[0],
                "antigen_code": key[1],
                "model": chosen,
                "reason": reason,
                **{f"mase_{m}": round(float(v), 4) for m, v in row.items()},
            }
        )
    return overall, per_vaccine, pd.DataFrame(choices)


def truth_bias(forecasts: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """Mean forecast minus true demand (evaluation only), in stock-out weeks and in other weeks."""
    t = truth.assign(week_start=pd.to_datetime(truth["week_start"]))[[*KEY, "week_start", "requested_doses"]]
    merged = forecasts.merge(t, on=[*KEY, "week_start"], how="left")
    merged["error_vs_true_demand"] = merged["yhat"] - merged["requested_doses"]
    return (
        merged.groupby(["model", "stockout_flag"])
        .agg(
            weeks=("yhat", "size"),
            mean_bias=("error_vs_true_demand", "mean"),
            mae_vs_true_demand=("error_vs_true_demand", lambda e: float(np.mean(np.abs(e)))),
        )
        .reset_index()
        .round(3)
    )


def manifest(series_sha: str, run_id: str, models: list[str], seed: int, repo: Path, n_weeks: int) -> dict:
    """What a training log entry needs: code version, data hash, settings, seed, software and hardware."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"
    versions = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    device = "cpu"
    try:
        import statsmodels

        versions["statsmodels"] = statsmodels.__version__
    except ImportError:
        pass
    try:
        import tensorflow as tf

        versions["tensorflow"] = tf.__version__
        gpus = tf.config.list_physical_devices("GPU")
        device = gpus[0].name if gpus else "cpu"
    except ImportError:
        pass
    return {
        "run_id": run_id,
        "series_sha256": series_sha,
        "git_commit": commit,
        "models": models,
        "seed": seed,
        "horizon_weeks": HORIZON,
        "test_weeks": TEST_WEEKS,
        "weeks": n_weeks,
        "origins": len(origins(n_weeks)),
        "versions": versions,
        "device": device,
        "host": platform.node(),
    }


def train_final(series: pd.DataFrame, selection: pd.DataFrame, seed: int, out: Path) -> pd.DataFrame:
    """Fit each series' selected model on all weeks and forecast the next HORIZON weeks; the GRU is saved to
    `out`, SARIMA orders are kept in the `detail` column (a refit from them is fast). A selection made only
    of baselines fits nothing and runs anywhere."""
    chosen = {(r.facility_code, r.antigen_code): r.model for r in selection.itertuples()}
    if FITTED & set(chosen.values()):
        require_training_host("Final training")
    weeks = pd.DatetimeIndex(sorted(series["week_start"].unique()))
    grouped = _grouped(series)
    future = pd.date_range(weeks[-1], periods=HORIZON + 1, freq="W-MON")[1:]
    rows = []
    for model in sorted(set(chosen.values())):
        forecasts = _forecast_all(model, grouped, len(weeks), weeks, seed, save_dir=out)
        for key, fc in forecasts.items():
            if chosen.get(key) != model:
                continue
            for h in range(HORIZON):
                rows.append(
                    {
                        "facility_code": key[0],
                        "antigen_code": key[1],
                        "model": model,
                        "week_start": future[h].date(),
                        "horizon_week": h + 1,
                        "yhat": round(float(fc.yhat[h]), 2),
                        "lo80": round(float(fc.lo80[h]), 2),
                        "hi80": round(float(fc.hi80[h]), 2),
                        "detail": json.dumps(fc.detail, default=str),
                    }
                )
    return pd.DataFrame(rows)
