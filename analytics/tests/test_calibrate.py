"""Second-stage calibration (D-26): damped steps and the stop rule inputs."""

import math

import pytest

from immdss_analytics.sim.behaviour import initial_params
from immdss_analytics.sim.calibrate import anchors, refine
from immdss_analytics.sim.config import parse_config


def coverage_at(cfg, factor: float) -> dict[str, float]:
    """Every indicator at `factor` times its KDHS target, in percent."""
    targets = cfg.section("calibration")["targets"]
    return {k: 100 * v * factor for k, v in targets.items()}


@pytest.mark.parametrize("damping", [1.0, 0.5])
def test_give_prob_step_is_damped(raw, damping):
    raw["calibration"]["engine_damping"] = damping
    cfg = parse_config(raw)
    params = initial_params(cfg)
    dose = next(d for d in cfg.dose_rules if d not in set(anchors(cfg).values()) and d != "OPV-0")
    params.give_prob[dose] = 0.5
    refined = refine(cfg, params, coverage_at(cfg, 0.9))
    assert refined.give_prob[dose] == pytest.approx(0.5 * (1 / 0.9) ** damping)


def test_damping_scales_attendance_step(raw):
    steps = []
    for damping in (1.0, 0.5):
        raw["calibration"]["engine_damping"] = damping
        cfg = parse_config(raw)
        params = initial_params(cfg)
        before = list(params.attend)
        after = refine(cfg, params, coverage_at(cfg, 0.95)).attend
        steps.append([a - b for a, b in zip(after, before, strict=True)])
    moved = [i for i, s in enumerate(steps[0]) if abs(s) > 1e-9]
    assert moved
    for i in moved:
        assert steps[1][i] == pytest.approx(0.5 * steps[0][i])
        assert not math.isnan(steps[1][i])


def test_on_target_coverage_changes_nothing(raw):
    raw["calibration"]["engine_damping"] = 0.6
    cfg = parse_config(raw)
    params = initial_params(cfg)
    before = (params.entry, list(params.attend), dict(params.give_prob))
    refined = refine(cfg, params, coverage_at(cfg, 1.0))
    assert refined.entry == pytest.approx(before[0])
    assert refined.attend == pytest.approx(before[1])
    assert refined.give_prob == pytest.approx(before[2])
