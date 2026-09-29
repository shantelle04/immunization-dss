"""Forecast metrics exactly as defined in doc 05 section 1 (MAE, MASE, sMAPE, interval coverage)."""

from __future__ import annotations

import numpy as np

SEASON = 52


def mae(actual: np.ndarray, forecast: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(actual, float) - np.asarray(forecast, float))))


def naive_scale(train: np.ndarray, season: int = SEASON) -> float:
    """In-sample MAE of the seasonal naive forecast (lag 52), the MASE denominator.

    With less than a season of history the lag-1 naive is used. A zero scale (a constant series) returns nan,
    so MASE is reported as undefined rather than infinite.
    """
    train = np.asarray(train, float)
    lag = season if len(train) > season else 1
    if len(train) <= lag:
        return float("nan")
    scale = float(np.mean(np.abs(train[lag:] - train[:-lag])))
    return scale if scale > 0 else float("nan")


def mase(actual: np.ndarray, forecast: np.ndarray, train: np.ndarray) -> float:
    return mae(actual, forecast) / naive_scale(train)


def smape(actual: np.ndarray, forecast: np.ndarray) -> float:
    """Mean of 2|y - yhat| / (|y| + |yhat|); a week where both are 0 counts as a perfect forecast."""
    a, f = np.asarray(actual, float), np.asarray(forecast, float)
    denom = np.abs(a) + np.abs(f)
    terms = np.where(denom == 0, 0.0, 2 * np.abs(a - f) / np.where(denom == 0, 1, denom))
    return float(np.mean(terms))


def coverage(actual: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """Share of actual values inside the 80% interval [lo, hi]."""
    a = np.asarray(actual, float)
    return float(np.mean((a >= np.asarray(lo, float)) & (a <= np.asarray(hi, float))))
