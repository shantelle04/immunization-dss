"""Global GRU forecaster across all series (doc 05): one model learns from every facility and vaccine.

Inputs per week: the series scaled by its own training mean, the ledger stock-out flag (T-03) and the week of
the year (sine and cosine), plus one-hot facility and vaccine identities. Output: the 10th, 50th and 90th
percentile for each of the next `horizon` weeks, trained with the quantile (pinball) loss, so the 80% interval
comes from the model itself. Scaling uses training weeks only; TensorFlow loads on the training host only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import Forecast

QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class GruParams:
    lookback: int = 26
    units: int = 64
    epochs: int = 60
    batch_size: int = 128
    learning_rate: float = 1e-3
    patience: int = 6
    validation_share: float = 0.15


def _features(values, flags, weeks, key_onehot, scale):
    """Rows of shape (lookback, features) ending at every possible cut point."""
    week_of_year = np.array([w.isocalendar()[1] for w in weeks], float)
    angle = 2 * np.pi * week_of_year / 52.0
    per_week = np.column_stack([values / scale, flags.astype(float), np.sin(angle), np.cos(angle)])
    static = np.repeat(key_onehot[None, :], len(values), axis=0)
    return np.hstack([per_week, static])


def _windows(feats, target, lookback, horizon):
    xs, ys, ends = [], [], []
    for end in range(lookback, len(target) - horizon + 1):
        xs.append(feats[end - lookback : end])
        ys.append(target[end : end + horizon])
        ends.append(end)
    return xs, ys, ends


def fit_and_forecast(series: dict, weeks, horizon: int, seed: int, params: GruParams | None = None) -> dict:
    """`series` maps (facility, antigen) to (values, flags) over the training weeks; returns Forecasts.

    Training windows never overlap the validation weeks (a window's targets end before the cut week).
    """
    import tensorflow as tf

    params = params or GruParams()
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()

    keys = sorted(series)
    facilities = sorted({k[0] for k in keys})
    antigens = sorted({k[1] for k in keys})
    onehots = {}
    for key in keys:
        vec = np.zeros(len(facilities) + len(antigens))
        vec[facilities.index(key[0])] = 1
        vec[len(facilities) + antigens.index(key[1])] = 1
        onehots[key] = vec

    xs, ys, ends, last_inputs, scales = [], [], [], {}, {}
    for key in keys:
        values, flags = (np.asarray(a) for a in series[key])
        scale = float(values.mean()) + 1.0
        scales[key] = scale
        feats = _features(values.astype(float), flags, weeks, onehots[key], scale)
        wx, wy, we = _windows(feats, values / scale, params.lookback, horizon)
        xs += wx
        ys += wy
        ends += we
        last_inputs[key] = feats[-params.lookback :]
    x, y = np.asarray(xs, "float32"), np.asarray(ys, "float32")

    # Early stopping watches the most recent weeks of every series (a time-based hold-out, no shuffling).
    ends_arr = np.asarray(ends)
    cut_week = int(len(weeks) * (1 - params.validation_share))
    train_idx, val_idx = np.flatnonzero(ends_arr + horizon <= cut_week), np.flatnonzero(ends_arr >= cut_week)
    inputs = tf.keras.Input(shape=x.shape[1:])
    hidden = tf.keras.layers.GRU(params.units)(inputs)
    hidden = tf.keras.layers.Dense(params.units, activation="relu")(hidden)
    outputs = tf.keras.layers.Reshape((horizon, len(QUANTILES)))(
        tf.keras.layers.Dense(horizon * len(QUANTILES))(hidden)
    )
    model = tf.keras.Model(inputs, outputs)

    q = tf.constant(QUANTILES, dtype=tf.float32)

    def pinball(y_true, y_pred):
        error = tf.expand_dims(y_true, -1) - y_pred
        return tf.reduce_mean(tf.maximum(q * error, (q - 1) * error))

    model.compile(optimizer=tf.keras.optimizers.Adam(params.learning_rate), loss=pinball)
    history = model.fit(
        x[train_idx],
        y[train_idx],
        validation_data=(x[val_idx], y[val_idx]),
        epochs=params.epochs,
        batch_size=params.batch_size,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=params.patience, restore_best_weights=True)],
        verbose=0,
    )
    predictions = model.predict(np.asarray([last_inputs[k] for k in keys], "float32"), verbose=0)
    out = {}
    for key, pred in zip(keys, predictions, strict=True):
        pred = np.sort(pred, axis=1) * scales[key]
        pred = np.clip(pred, 0, None)
        out[key] = Forecast(
            pred[:, 1],
            pred[:, 0],
            pred[:, 2],
            "gru",
            {
                "epochs_run": len(history.history["loss"]),
                "best_val_loss": float(min(history.history["val_loss"])),
            },
        )
    out["_model"] = model
    return out
