"""Per-series forecasters: B1 seasonal naive, B2 moving average (baselines, doc 05) and SARIMA (D-36).

Each returns a Forecast of `horizon` weeks with an 80% interval. Forecasts are clipped at zero (doses cannot
be negative). SARIMA imports statsmodels only when used, and only runs on the training host (D-14).
"""

from __future__ import annotations

import itertools
import warnings
from dataclasses import dataclass, field

import numpy as np

from .metrics import SEASON

MA_WINDOW = 4  # B2: mean of the last 4 weeks (doc 05)
SHORT_HISTORY_WINDOW = 4  # B1 fallback when there is less than one season of history
SARIMA_ORDERS = [(1, 0, 0), (0, 1, 1), (1, 1, 1), (2, 0, 1)]
# Yearly seasonality as Fourier terms (D-36): a seasonal AR term at lag 52 makes every state-space fit slow
# enough that 84 series x 6 origins would take hours; K harmonics of the 52.18-week year add 2K regressors.
FOURIER_OPTIONS = [0, 2]
YEAR_WEEKS = 365.25 / 7


@dataclass
class Forecast:
    yhat: np.ndarray
    lo80: np.ndarray
    hi80: np.ndarray
    model: str
    detail: dict = field(default_factory=dict)


def _residual_interval(point: np.ndarray, residuals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """80% interval from the 10th and 90th percentiles of in-sample one-step residuals."""
    if len(residuals) < 5:
        spread = np.full_like(point, max(1.0, float(np.std(point)) if len(point) > 1 else 1.0))
        return np.clip(point - spread, 0, None), point + spread
    lo_q, hi_q = np.quantile(residuals, [0.1, 0.9])
    return np.clip(point + lo_q, 0, None), np.clip(point + hi_q, 0, None)


def seasonal_naive(train: np.ndarray, horizon: int) -> Forecast:
    train = np.asarray(train, float)
    if len(train) >= SEASON + horizon:
        point = train[len(train) - SEASON : len(train) - SEASON + horizon]
        residuals = train[SEASON:] - train[:-SEASON]
        detail = {"rule": "same week last year"}
    else:
        point = np.full(horizon, float(np.mean(train[-SHORT_HISTORY_WINDOW:])))
        residuals = np.diff(train)
        detail = {"rule": f"short history: mean of last {SHORT_HISTORY_WINDOW} weeks"}
    point = np.clip(point, 0, None)
    lo, hi = _residual_interval(point, residuals)
    return Forecast(point, lo, hi, "seasonal_naive", detail)


def moving_average(train: np.ndarray, horizon: int, window: int = MA_WINDOW) -> Forecast:
    train = np.asarray(train, float)
    point = np.full(horizon, float(np.mean(train[-window:])))
    fitted = np.convolve(train, np.ones(window) / window, mode="valid")[:-1]
    residuals = train[window:] - fitted
    lo, hi = _residual_interval(point, residuals)
    return Forecast(point, lo, hi, "moving_average", {"window": window})


def fourier_terms(start: int, length: int, harmonics: int) -> np.ndarray | None:
    """sin and cos of the first `harmonics` yearly frequencies for weeks start .. start + length - 1."""
    if not harmonics:
        return None
    t = np.arange(start, start + length, dtype=float)
    k = np.arange(1, harmonics + 1)
    angle = 2 * np.pi * np.outer(t, k) / YEAR_WEEKS
    return np.hstack([np.sin(angle), np.cos(angle)])


def sarima(train: np.ndarray, horizon: int) -> Forecast:
    """ARIMA with Fourier yearly seasonality; order and harmonics chosen by AIC on the training window."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    train = np.asarray(train, float)
    best = None
    for order, harmonics in itertools.product(SARIMA_ORDERS, FOURIER_OPTIONS):
        if harmonics and len(train) < SEASON:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = SARIMAX(
                    train,
                    exog=fourier_terms(0, len(train), harmonics),
                    order=order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(disp=False)
        except (ValueError, np.linalg.LinAlgError):
            continue
        if np.isfinite(fit.aic) and (best is None or fit.aic < best[0]):
            best = (fit.aic, order, harmonics, fit)
    if best is None:
        fallback = seasonal_naive(train, horizon)
        fallback.detail["sarima"] = "no order converged; seasonal naive used"
        return fallback
    aic, order, harmonics, fit = best
    result = fit.get_forecast(horizon, exog=fourier_terms(len(train), horizon, harmonics))
    point = np.clip(result.predicted_mean, 0, None)
    interval = result.conf_int(alpha=0.2)
    lo, hi = np.clip(interval[:, 0], 0, None), np.clip(interval[:, 1], 0, None)
    return Forecast(
        point, lo, hi, "sarima", {"order": order, "fourier_harmonics": harmonics, "aic": round(aic, 2)}
    )


PER_SERIES = {"b1": seasonal_naive, "b2": moving_average, "sarima": sarima}
FITTED = {"sarima", "gru"}
