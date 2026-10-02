"""Forecast runs (FR-12, FR-13, FR-15, FR-16): the only backend module that calls the analytics package.

The weekly series is rebuilt from the database ledger with the same function the training pipeline uses, so
its SHA-256 can be compared with the series a Colab result was trained on. Model fitting never happens
here (D-14): a run either imports the files a Colab run produced, or uses the two baselines, which fit
nothing.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.db import transaction
from django.utils import timezone
from immdss_analytics.forecast import alerts as alert_rule
from immdss_analytics.forecast import backtest as bt
from immdss_analytics.forecast.series import build_weekly_series, series_sha256

from apps.facilities.models import Facility
from apps.passport.models import Antigen

from .models import (
    AlertStatus,
    Forecast,
    ForecastModel,
    ForecastRun,
    StockAlert,
    StockPolicy,
    StockTransaction,
)

MODEL_NAMES = {
    "b1": ForecastModel.SEASONAL_NAIVE.value,
    "b2": ForecastModel.MOVING_AVERAGE.value,
    "sarima": ForecastModel.SARIMA.value,
    "gru": ForecastModel.GRU.value,
}
BASELINES = ["b1", "b2"]
MIN_WEEKS_FOR_BACKTEST = bt.TEST_WEEKS + 8
KEY = ["facility_code", "antigen_code"]


class ForecastRefused(Exception):
    pass


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def ledger_frame() -> pd.DataFrame:
    rows = StockTransaction.objects.values_list(
        "occurred_on", "facility__code", "antigen__code", "kind", "quantity_doses"
    )
    return pd.DataFrame(list(rows), columns=["date", *KEY, "kind", "quantity_doses"])


def weekly_series(ledger: pd.DataFrame, on: date) -> pd.DataFrame:
    """Complete weeks before the week that contains `on`."""
    start = monday(pd.to_datetime(ledger["date"]).min().date())
    return build_weekly_series(ledger, start, monday(on))


def _baseline_results(series: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weeks = series["week_start"].nunique()
    if weeks < MIN_WEEKS_FOR_BACKTEST:
        keys = series[KEY].drop_duplicates()
        selection = keys.assign(model="b2", reason="short history: moving average")
        return selection, pd.DataFrame(), bt.train_final(series, selection, seed, None)
    metrics = bt.score(bt.run_backtest(series, BASELINES, seed), series)
    selection = bt.compare(metrics)[2]
    return selection, metrics, bt.train_final(series, selection, seed, None)


def _imported_results(results: Path, sha: str, first_week: date):
    manifest = json.loads((results / "manifest.json").read_text())
    if manifest["series_sha256"] != sha:
        raise ForecastRefused(
            "These results were trained on a different series than the one in the database "
            f"(trained {manifest['series_sha256'][:12]}, database {sha[:12]}). Retrain, or reload the data."
        )
    selection = pd.read_csv(results / "selection.csv")
    metrics = pd.read_csv(results / "metrics.csv")
    final = pd.read_csv(results / "final_forecasts.csv", parse_dates=["week_start"])
    if final["week_start"].min().date() != first_week:
        raise ForecastRefused("The imported forecasts do not start at the current week.")
    return selection, metrics, final, manifest


def _clean(value):
    return None if isinstance(value, float) and pd.isna(value) else value


def _metrics_payload(metrics: pd.DataFrame, selection: pd.DataFrame) -> dict:
    """Backtest accuracy of the selected model per series, and the overall comparison (JSON safe)."""
    if metrics.empty:
        return {"by_series": {}, "overall": []}
    picked = metrics.merge(selection[[*KEY, "model"]], on=[*KEY, "model"])
    by_series = {
        f"{r.facility_code}|{r.antigen_code}": {
            "model": MODEL_NAMES[r.model],
            "mase": _clean(float(r.mase)),
            "mae": float(r.mae),
            "smape": float(r.smape),
            "coverage80": float(r.coverage80),
        }
        for r in picked.itertuples()
    }
    overall = []
    for row in bt.compare(metrics)[0].to_dict("records"):
        overall.append({k: _clean(v) for k, v in row.items()} | {"model": MODEL_NAMES[row["model"]]})
    return {"by_series": by_series, "overall": overall}


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


@transaction.atomic
def run(on: date, results: Path | None = None, seed: int = 42) -> ForecastRun:
    """Build the series, take forecasts (imported or baseline), store them and refresh the alerts."""
    ledger = ledger_frame()
    if ledger.empty:
        raise ForecastRefused("The stock ledger is empty; load data first.")
    series = weekly_series(ledger, on)
    sha = series_sha256(series)
    if results is not None:
        selection, metrics, final, manifest = _imported_results(results, sha, monday(on))
        source = {"source": "colab", "training_commit": manifest["git_commit"], "device": manifest["device"]}
    else:
        selection, metrics, final = _baseline_results(series, seed)
        source = {"source": "baselines"}
    forecast_run = ForecastRun.objects.create(
        run_at=timezone.now(),
        git_sha=_git_sha(),
        data_sha256=sha,
        params={
            **source,
            "seed": seed,
            "as_of": on.isoformat(),
            "horizon_weeks": bt.HORIZON,
            "series": int(series.groupby(KEY).ngroups),
            "weeks": int(series["week_start"].nunique()),
            "models": selection["model"].map(MODEL_NAMES).value_counts().to_dict(),
        },
        metrics=_metrics_payload(metrics, selection),
    )
    facilities = dict(Facility.objects.values_list("code", "id"))
    antigens = dict(Antigen.objects.values_list("code", "id"))
    final = final.assign(week_start=pd.to_datetime(final["week_start"]))
    Forecast.objects.bulk_create(
        Forecast(
            run=forecast_run,
            facility_id=facilities[r.facility_code],
            antigen_id=antigens[r.antigen_code],
            week_start=r.week_start.date(),
            horizon_week=r.horizon_week,
            yhat=Decimal(str(round(r.yhat, 2))),
            lo80=Decimal(str(round(r.lo80, 2))),
            hi80=Decimal(str(round(r.hi80, 2))),
            model=MODEL_NAMES[r.model],
        )
        for r in final.itertuples()
    )
    _refresh_alerts(forecast_run, ledger, final, on, facilities, antigens)
    return forecast_run


def _refresh_alerts(forecast_run, ledger, final, on, facilities, antigens) -> None:
    """BR-05 for every series: raise, keep (with its acknowledgement) or resolve the alert."""
    tx = ledger.assign(date=pd.to_datetime(ledger["date"]))
    tx_by_series = {k: g for k, g in tx.groupby(KEY)}
    policies = {(p.facility_id, p.antigen_id): p for p in StockPolicy.objects.all()}
    active = {
        (a.facility_id, a.antigen_id): a
        for a in StockAlert.objects.select_for_update().exclude(status=AlertStatus.RESOLVED)
    }
    # Everything recorded up to and including today counts as current stock.
    origin = pd.Timestamp(on) + pd.DateOffset(days=1)
    for (fac, ant), g in final.groupby(KEY):
        key = (facilities[fac], antigens[ant])
        policy = policies.get(key)
        cycle = policy.cycle_weeks if policy else alert_rule.DEFAULT_CYCLE_WEEKS
        buffer = float(policy.safety_buffer) if policy else alert_rule.DEFAULT_BUFFER
        state = alert_rule.series_state(tx_by_series[(fac, ant)], origin)
        upper = list(g.sort_values("horizon_week")["hi80"])
        _, breach = alert_rule.breach_for(state, upper, on, cycle, buffer)
        existing = active.get(key)
        if breach is None:
            if existing:
                existing.status = AlertStatus.RESOLVED
                existing.save(update_fields=["status", "updated_at"])
            continue
        values = {
            "run": forecast_run,
            "projected_breach_week": monday(on) + timedelta(weeks=breach.week_ahead - 1),
            "projected_doses": Decimal(str(breach.projected_doses)),
            "safety_minimum": Decimal(str(breach.safety_minimum)),
        }
        if existing:
            for name, value in values.items():
                setattr(existing, name, value)
            existing.save()
        else:
            StockAlert.objects.create(facility_id=key[0], antigen_id=key[1], raised_on=on, **values)
