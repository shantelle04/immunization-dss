"""Forecast pipeline, local part (D-14): series building and cleaning, metrics, baselines, splits, scoring and
selection. Model fitting (SARIMA, GRU) is refused here and runs only on Colab."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from immdss_analytics.forecast import alerts, guard
from immdss_analytics.forecast import backtest as bt
from immdss_analytics.forecast.gru import conformal_margin
from immdss_analytics.forecast.guard import TrainingRefused
from immdss_analytics.forecast.metrics import coverage, mae, mase, naive_scale, smape
from immdss_analytics.forecast.models import fourier_terms, moving_average, seasonal_naive
from immdss_analytics.forecast.series import SERIES_COLUMNS, build_weekly_series

START, END = dt.date(2021, 1, 4), dt.date(2021, 2, 1)  # four Monday weeks


def _ledger(rows):
    return pd.DataFrame(rows, columns=["date", "facility_code", "antigen_code", "kind", "quantity_doses"])


def test_series_counts_issues_per_week_and_fills_empty_weeks_with_zero():
    ledger = _ledger(
        [
            ("2021-01-04", "F1", "BCG", "opening_balance", 20),
            ("2021-01-05", "F1", "BCG", "issue", -3),
            ("2021-01-07", "F1", "BCG", "issue", -2),
            ("2021-01-19", "F1", "BCG", "issue", -4),
            ("2021-01-19", "F1", "BCG", "wastage", -5),
        ]
    )
    frame = build_weekly_series(ledger, START, END)
    assert list(frame["issued"]) == [5, 0, 4, 0], "wastage is not demand; empty weeks are 0 (T-01)"
    assert list(frame["week_start"].dt.date) == [START + dt.timedelta(weeks=i) for i in range(4)]


def test_stockout_flag_comes_from_the_ledger_balance():
    ledger = _ledger(
        [
            ("2021-01-04", "F1", "MR", "opening_balance", 3),
            ("2021-01-12", "F1", "MR", "issue", -3),
            ("2021-01-19", "F1", "MR", "receipt", 10),
        ]
    )
    flags = list(build_weekly_series(ledger, START, END)["stockout_flag"])
    assert flags == [False, True, False, False], "T-03: balance reached zero in week 2 only"


def test_weeks_outside_the_stock_window_are_dropped():
    ledger = _ledger(
        [
            ("2020-12-28", "F1", "BCG", "issue", -9),
            ("2021-01-04", "F1", "BCG", "issue", -1),
            ("2021-02-01", "F1", "BCG", "issue", -9),
        ]
    )
    assert build_weekly_series(ledger, START, END)["issued"].sum() == 1


def test_metrics_follow_doc_05():
    actual, forecast = np.array([2, 0, 4]), np.array([1, 0, 5])
    assert mae(actual, forecast) == pytest.approx(2 / 3)
    assert smape(actual, forecast) == pytest.approx((2 / 3 + 0 + 2 / 9) / 3)
    assert coverage(actual, np.array([1, 0, 0]), np.array([3, 0, 3])) == pytest.approx(2 / 3)
    train = np.arange(60, dtype=float)
    assert naive_scale(train) == pytest.approx(52.0)
    assert mase(actual, forecast, train) == pytest.approx((2 / 3) / 52)
    assert np.isnan(naive_scale(np.ones(60)))


def test_fourier_terms_continue_the_training_calendar_into_the_forecast():
    whole = fourier_terms(0, 10, 2)
    assert whole.shape == (10, 4)
    assert np.allclose(fourier_terms(6, 4, 2), whole[6:])
    assert fourier_terms(0, 10, 0) is None


def test_seasonal_naive_repeats_last_year_and_falls_back_on_short_history():
    train = np.arange(104, dtype=float)
    assert list(seasonal_naive(train, 4).yhat) == [52, 53, 54, 55]
    short = seasonal_naive(np.array([2.0, 4, 6, 8, 10]), 4)
    assert list(short.yhat) == [7, 7, 7, 7] and "short history" in short.detail["rule"]


def test_moving_average_and_non_negative_intervals():
    fc = moving_average(np.array([0.0, 0, 1, 0, 2, 1, 0, 1]), 4)
    assert list(fc.yhat) == [1, 1, 1, 1]
    assert (fc.lo80 >= 0).all() and (fc.hi80 >= fc.yhat).all()


def test_origins_never_let_a_test_week_into_training():
    cuts = bt.origins(260)
    assert cuts == [236, 240, 244, 248, 252, 256]
    for cut in cuts:
        assert cut + bt.HORIZON <= 260


def _toy_series(n_weeks=120):
    weeks = pd.date_range("2021-01-04", periods=n_weeks, freq="W-MON")
    rng = np.random.default_rng(0)
    rows = []
    for fac in ("F1", "F2"):
        for ant in ("BCG", "MR"):
            base = 10 + 3 * np.sin(np.arange(n_weeks) * 2 * np.pi / 52)
            for w, v in zip(weeks, rng.poisson(base), strict=True):
                rows.append((fac, ant, w, int(v), False))
    return pd.DataFrame(rows, columns=SERIES_COLUMNS)


def test_baseline_backtest_scoring_and_selection_run_locally():
    series = _toy_series()
    forecasts = bt.run_backtest(series, ["b1", "b2"], seed=1)
    assert len(forecasts) == 2 * 4 * 6 * bt.HORIZON
    assert (pd.to_datetime(forecasts["week_start"]) >= pd.to_datetime(forecasts["origin_week"])).all()
    metrics = bt.score(forecasts, series)
    assert set(metrics["model"]) == {"b1", "b2"} and metrics["mase"].notna().all()
    overall, per_vaccine, selection = bt.compare(metrics)
    assert list(overall.columns)[:3] == ["model", "series", "mean_mase"]
    assert set(selection["model"]) <= {"b1", "b2"}
    assert (selection["reason"] == "fallback: better baseline").all()


def test_selection_prefers_gru_only_when_it_beats_seasonal_naive_with_enough_history():
    metrics = pd.DataFrame(
        [
            ("gru", "F1", "BCG", 0.8, 200),
            ("b1", "F1", "BCG", 1.0, 200),
            ("sarima", "F1", "BCG", 0.9, 200),
            ("gru", "F1", "MR", 1.2, 200),
            ("b1", "F1", "MR", 1.0, 200),
            ("sarima", "F1", "MR", 0.95, 200),
        ],
        columns=["model", "facility_code", "antigen_code", "mase", "min_train_weeks"],
    ).assign(mae=1.0, smape=0.1, coverage80=0.8)
    selection = bt.compare(metrics)[2].set_index("antigen_code")["model"].to_dict()
    assert selection == {"BCG": "gru", "MR": "sarima"}


def test_model_fitting_is_refused_off_colab(monkeypatch):
    monkeypatch.delenv("IMMDSS_ALLOW_TRAINING", raising=False)
    monkeypatch.setattr(guard.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(TrainingRefused, match="Colab"):
        bt.run_backtest(_toy_series(), ["b1", "sarima"], seed=1)
    with pytest.raises(TrainingRefused):
        selection = pd.DataFrame(
            [("F1", "BCG", "sarima")], columns=["facility_code", "antigen_code", "model"]
        )
        bt.train_final(_toy_series(), selection, 1, None)


def test_baseline_only_selection_forecasts_the_next_weeks_without_fitting(monkeypatch):
    monkeypatch.delenv("IMMDSS_ALLOW_TRAINING", raising=False)
    monkeypatch.setattr(guard.importlib.util, "find_spec", lambda name: None)
    series = _toy_series()
    selection = bt.compare(bt.score(bt.run_backtest(series, ["b1", "b2"], seed=1), series))[2]
    final = bt.train_final(series, selection, 1, None)
    assert len(final) == 4 * bt.HORIZON
    last = series["week_start"].max()
    assert pd.Timestamp(final["week_start"].min()) == last + pd.DateOffset(weeks=1)


def test_replenishment_cover_and_first_breach():
    on = dt.date(2025, 6, 2)
    assert alerts.weeks_to_replenishment(dt.date(2025, 5, 19), 4, on, 4) == 2
    assert alerts.weeks_to_replenishment(dt.date(2025, 4, 28), 4, on, 4) == 4, "late delivery: full horizon"
    assert alerts.weeks_to_replenishment(None, 4, on, 4) == 4
    assert alerts.first_breach(100, [10, 10, 10, 10], 10, 4, 0.25) is None
    breach = alerts.first_breach(30, [10, 10, 10, 10], 10, 4, 0.25)
    assert (breach.week_ahead, breach.projected_doses, breach.safety_minimum) == (1, 20, 37.5)
    assert alerts.first_breach(30, [10, 10, 10, 10], 10, 1, 0.25) is None, "replenished after one week"
    assert alerts.first_breach(5, [10, 10], 10, 1, 0.25).projected_doses == -5
    assert alerts.usage_factor(10, 30) == 4.0 and alerts.usage_factor(0, 5) == 1.0


def test_alert_decisions_use_only_data_before_the_origin_and_are_scored_against_truth():
    weeks = pd.date_range("2025-01-06", periods=20, freq="W-MON")
    origin = weeks[16]
    ledger = pd.DataFrame(
        [
            ("2025-01-06", "F1", "BCG", "opening_balance", 200),
            ("2025-01-06", "F2", "BCG", "opening_balance", 900),
        ]
        + [(str(w.date()), f, "BCG", "issue", -10) for w in weeks for f in ("F1", "F2")],
        columns=["date", "facility_code", "antigen_code", "kind", "quantity_doses"],
    )
    forecasts = pd.DataFrame(
        [
            ("b2", f, "BCG", origin, origin + pd.DateOffset(weeks=h), h + 1, 10.0, 12.0)
            for f in ("F1", "F2")
            for h in range(4)
        ],
        columns=["model", "facility_code", "antigen_code", "origin_week", "week_start", "h", "yhat", "hi80"],
    )
    selection = pd.DataFrame(
        [("F1", "BCG", "b2"), ("F2", "BCG", "b2")], columns=["facility_code", "antigen_code", "model"]
    )
    decisions = alerts.decide(ledger, forecasts, selection).set_index("facility_code")
    assert decisions.loc["F1", "stock_doses"] == 40 and decisions.loc["F2", "stock_doses"] == 740
    assert bool(decisions.loc["F1", "alert"]) and not bool(decisions.loc["F2", "alert"])
    truth = pd.DataFrame(
        [("F1", "BCG", origin + pd.DateOffset(weeks=h), max(40 - 10 * (h + 1), 0), h >= 3) for h in range(4)]
        + [("F2", "BCG", origin + pd.DateOffset(weeks=h), 700, False) for h in range(4)],
        columns=["facility_code", "antigen_code", "week_start", "closing_doses", "stockout"],
    )
    _, summary = alerts.evaluate(decisions.reset_index(), truth)
    assert summary["alerts"] == 1 and summary["recall"] == 1.0 and summary["precision"] == 1.0
    assert summary["mean_lead_time_weeks"] == 4.0


def test_conformal_margin_reaches_the_target_coverage_and_can_narrow():
    rng = np.random.default_rng(3)
    actual = rng.normal(0, 1, 2000)
    narrow_lo, narrow_hi = np.full(2000, -0.5), np.full(2000, 0.5)
    margin = conformal_margin(narrow_lo, narrow_hi, actual, 0.8)
    assert margin > 0
    assert coverage(actual, narrow_lo - margin, narrow_hi + margin) >= 0.8
    wide = conformal_margin(np.full(2000, -5.0), np.full(2000, 5.0), actual, 0.8)
    assert wide < 0, "an interval that is too wide is narrowed"
    assert coverage(actual, -5 - wide, 5 + wide) == pytest.approx(0.8, abs=0.01)
