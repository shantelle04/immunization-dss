"""Forecast pipeline, local part (D-14): series building and cleaning, metrics, baselines, splits, scoring and
selection. Model fitting (SARIMA, GRU) is refused here and runs only on Colab."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from immdss_analytics.forecast import alert_study, alerts, commands, guard
from immdss_analytics.forecast import backtest as bt
from immdss_analytics.forecast.gru import upper_margin
from immdss_analytics.forecast.guard import TrainingRefused
from immdss_analytics.forecast.metrics import coverage, mae, mase, naive_scale, smape
from immdss_analytics.forecast.models import fourier_terms, moving_average, seasonal_naive
from immdss_analytics.forecast.series import SERIES_COLUMNS, build_weekly_series, write_series

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
    assert flags == [False, True, True, False], "T-03: empty from week 2 until the Tuesday delivery in week 3"


def test_stockout_flag_covers_weeks_that_start_and_stay_at_zero():
    ledger = _ledger(
        [
            ("2021-01-04", "F1", "MR", "opening_balance", 3),
            ("2021-01-06", "F1", "MR", "issue", -3),
            ("2021-01-25", "F1", "MR", "receipt", 10),
        ]
    )
    flags = list(build_weekly_series(ledger, START, END)["stockout_flag"])
    assert flags == [True, True, True, False], "empty until a Monday delivery; that week is not flagged"


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


def test_late_delivery_check_looks_only_just_after_the_expected_delivery():
    upper = [10, 10, 10, 10]
    late = alerts.run_out_if_delivery_late(15, upper, cover_weeks=1, grace_weeks=1)
    assert (late.week_ahead, late.projected_doses) == (2, -5), "stock ends if the delivery is one week late"
    assert alerts.run_out_if_delivery_late(25, upper, 1, 1) is None, "stock lasts one late week"
    assert alerts.run_out_if_delivery_late(25, upper, 1, 2).week_ahead == 3
    assert alerts.run_out_if_delivery_late(5, upper, 4, 1) is None, "nothing to check beyond the horizon"


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


def test_upper_margin_sets_the_exceedance_rate_and_can_lower_the_bound():
    rng = np.random.default_rng(3)
    actual = rng.normal(0, 1, 2000)
    low = upper_margin(np.zeros(2000), actual, 0.9)
    assert low > 0
    assert (actual <= low).mean() >= 0.9
    high = upper_margin(np.full(2000, 5.0), actual, 0.9)
    assert high < 0, "an upper end that is too high is lowered"
    assert (actual <= 5 + high).mean() == pytest.approx(0.9, abs=0.01)


def _study_data():
    """Two series over 40 weeks: F1 gets a delivery every 4 weeks, F2 every 6 and runs dry in between."""
    weeks = pd.date_range("2025-01-06", periods=40, freq="W-MON")
    start = str(weeks[0].date())
    rows = [(start, "F1", "BCG", "opening_balance", 80), (start, "F2", "BCG", "opening_balance", 40)]
    for i, w in enumerate(weeks):
        for fac, every in (("F1", 4), ("F2", 6)):
            if i and i % every == 0:
                rows.append((str(w.date()), fac, "BCG", "receipt", 40))
            if fac == "F1" or i % every < 4:
                rows.append((str((w + pd.DateOffset(days=1)).date()), fac, "BCG", "issue", -10))
    ledger = pd.DataFrame(rows, columns=["date", "facility_code", "antigen_code", "kind", "quantity_doses"])
    series = build_weekly_series(ledger, weeks[0].date(), (weeks[-1] + pd.DateOffset(weeks=1)).date())
    return ledger, series


def test_weekly_origins_leave_a_full_horizon_and_tuning_weeks_precede_test_weeks():
    test, tune = alert_study.weekly_origins(260, 24), alert_study.weekly_origins(260, 48, 24)
    assert (test[0], test[-1], len(test)) == (236, 256, 21)
    assert (tune[0], tune[-1]) == (212, 232) and tune[-1] + bt.HORIZON <= test[0]


def test_late_rate_counts_intervals_more_than_a_week_over_the_cycle():
    assert alert_study.late_rate(np.array([0, 4, 8, 12]), 4) == 0.0
    assert alert_study.late_rate(np.array([0, 4, 10, 14, 20]), 4) == 0.5
    assert alert_study.late_rate(np.array([3]), 4) == 0.0


def test_features_use_only_weeks_before_the_decision_and_label_only_weeks_after():
    ledger, series = _study_data()
    frame = alert_study.features(ledger, series, [20, 28, 38]).set_index(["facility_code", "origin"])
    f1, f2 = frame.loc[("F1", 20)], frame.loc[("F2", 28)]
    assert f1["stock_doses"] == 80 + 40 * 4 - 10 * 20 and f1["late_rate"] == 0 and f1["label"] == 0
    assert f2["late_rate"] == 1.0 and f2["recent_stockout_weeks"] > 0 and f2["label"] == 1
    assert np.isnan(frame.loc[("F1", 38), "label"]), "the horizon runs past the data: no label"
    earlier = ledger[pd.to_datetime(ledger["date"]) < "2025-05-26"]
    cut = alert_study.features(earlier, series, [20]).set_index(["facility_code", "origin"])
    assert cut.loc[("F1", 20), "stock_doses"] == f1["stock_doses"], "later transactions change nothing"


def test_weekly_scoring_separates_early_warning_from_alerts_in_the_stock_out_week():
    weeks = pd.date_range("2025-06-02", periods=6, freq="W-MON")
    truth = pd.DataFrame(
        [
            ("F1", "BCG", w, i in (3, 4))
            for i, w in enumerate(pd.date_range(weeks[0], periods=9, freq="W-MON"))
        ],
        columns=["facility_code", "antigen_code", "week_start", "stockout"],
    )

    def decisions(flags):
        return pd.DataFrame(
            {"facility_code": "F1", "antigen_code": "BCG", "origin_week": weeks, "alert": flags}
        )

    early = alert_study.evaluate_weekly(decisions([False, True, False, False, False, False]), truth)
    assert (early["recall"], early["early_recall"], early["onset_early_recall"]) == (1.0, 1.0, 1.0)
    assert (early["true_stockout_weeks"], early["onsets"], early["precision_stockout_only"]) == (2, 1, 1.0)
    assert early["base_rate"] == pytest.approx(5 / 6, abs=1e-4)
    same_week = alert_study.evaluate_weekly(decisions([False, False, False, True, False, False]), truth)
    assert same_week["recall"] == 1.0 and same_week["early_recall"] == 0.5
    assert same_week["onset_early_recall"] == 0.0, "an alert in the week stock runs out is not a warning"
    silent = alert_study.evaluate_weekly(decisions([False] * 6), truth)
    assert silent["recall"] == 0.0 and silent["flagged"] == 0


def test_late_rate_gate_is_the_strictest_one_that_reaches_the_target_on_ledger_labels():
    frame = pd.DataFrame({"late_rate": [0.0, 0.0, 0.5, 0.5, 1.0], "label": [0, 1, 1, 1, 1]})
    base = pd.Series([False, True, False, False, False])
    late = pd.Series([True, False, True, True, True])
    assert alert_study.pick_late_rate_gate(frame, base, late) == 0.5
    assert alert_study.pick_late_rate_gate(frame, base, pd.Series([False] * 5)) == 0.0


def test_risk_score_is_refused_off_colab(monkeypatch):
    monkeypatch.delenv("IMMDSS_ALLOW_TRAINING", raising=False)
    monkeypatch.setattr(guard.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(TrainingRefused):
        alert_study.fit_risk_score(pd.DataFrame(), pd.DataFrame(), 1)


class _StandInModel:
    """Scores by how little stock is left; stands in for the fitted model so nothing is trained here."""

    def predict_proba(self, features):
        risk = 1 / (1 + features["weeks_of_stock"].to_numpy())
        return np.column_stack([1 - risk, risk])


def test_alert_study_runs_end_to_end_with_a_stand_in_risk_model(tmp_path, monkeypatch):
    weeks = pd.date_range("2023-01-02", periods=130, freq="W-MON")
    rng = np.random.default_rng(5)
    rows = [(str(weeks[0].date()), f, "BCG", "opening_balance", 30) for f in ("F1", "F2")]
    for i, w in enumerate(weeks):
        for fac, delivered in (("F1", 45), ("F2", 32)):
            if i and i % 4 == 0:
                rows.append((str(w.date()), fac, "BCG", "receipt", delivered))
    ledger = pd.DataFrame(rows, columns=["date", "facility_code", "antigen_code", "kind", "quantity_doses"])
    stock = {"F1": 30, "F2": 30}
    issues = []
    for i, w in enumerate(weeks):
        for fac, delivered in (("F1", 45), ("F2", 32)):
            stock[fac] += delivered if i and i % 4 == 0 else 0
            used = min(stock[fac], int(rng.poisson(9)))
            stock[fac] -= used
            if used:
                issues.append((str((w + pd.DateOffset(days=2)).date()), fac, "BCG", "issue", -used))
    ledger = pd.concat([ledger, pd.DataFrame(issues, columns=ledger.columns)])
    run = tmp_path / "run"
    (run / "app").mkdir(parents=True)
    (run / "truth").mkdir()
    ledger.to_csv(run / "app" / "stock_transactions.csv", index=False)
    (run / "manifest.json").write_text('{"run_id": "toy"}')
    series = build_weekly_series(ledger, weeks[0].date(), (weeks[-1] + pd.DateOffset(weeks=1)).date())
    truth = series.rename(columns={"stockout_flag": "stockout"})[
        ["facility_code", "antigen_code", "week_start", "stockout"]
    ]
    truth.to_csv(run / "truth" / "weekly_stock.csv", index=False)
    sha = write_series(series, tmp_path / "series" / "weekly_issues.csv")
    (tmp_path / "series" / "series_manifest.json").write_text(f'{{"sha256": "{sha}"}}')
    results = tmp_path / "results"
    results.mkdir()
    selection = series[["facility_code", "antigen_code"]].drop_duplicates().assign(model="b2")
    selection.to_csv(results / "selection.csv", index=False)

    seen = {}

    def stand_in_fit(train, tune, seed):
        seen["train"], seen["tune"] = train, tune
        return _StandInModel(), 0.4, {"stand_in": True}

    monkeypatch.setattr(alert_study, "on_training_host", lambda: True)
    monkeypatch.setattr(alert_study, "fit_risk_score", stand_in_fit)
    out = commands.run_alert_study(
        run, tmp_path / "series" / "weekly_issues.csv", results, 1, tmp_path / "out"
    )
    table = pd.read_csv(out / "alert_study.csv").set_index("method")
    assert {"rule, weekly decisions", "risk score", "risk score or rule"} <= set(table.index)
    assert table.loc["risk score", "decisions"] == 2 * 21
    for frame in seen.values():
        assert set(alert_study.FEATURES) <= set(frame.columns), "training and scoring share every feature"
    assert seen["train"]["origin"].max() + bt.HORIZON <= seen["tune"]["origin"].min(), "labels do not overlap"
    decisions = pd.read_csv(out / "weekly_decisions.csv")
    assert decisions["risk"].between(0, 1).all() and decisions["risk_flag"].isin([True, False]).all()
