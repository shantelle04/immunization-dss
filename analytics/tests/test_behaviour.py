import numpy as np

from immdss_analytics.sim.behaviour import CLOSED, Params, Series, offer, record_given
from immdss_analytics.sim.config import parse_config


def setup(raw):
    cfg = parse_config(raw)
    params = Params(entry=5.0, attend=[5.0] * len(cfg.contacts), give_prob={d: 1.0 for d in cfg.dose_rules})
    return cfg, Series.from_config(cfg), params, np.random.default_rng(0)


def test_birth_visit_offers_bcg_and_opv0(raw):
    cfg, series, params, rng = setup(raw)
    nxt, last = dict(series.first_number), {}
    assert sorted(offer(cfg, series, params, rng, 1003, 1000, nxt, last)) == ["BCG-1", "OPV-0"]


def test_late_first_visit_skips_opv0_and_catches_up_bcg(raw):
    cfg, series, params, rng = setup(raw)
    nxt, last = dict(series.first_number), {}
    doses = offer(cfg, series, params, rng, 1000 + 45, 1000, nxt, last)
    assert "OPV-0" not in doses
    assert {"BCG-1", "OPV-1", "PENTA-1", "PCV-1", "ROTA-1"} <= set(doses)


def test_min_interval_blocks_next_dose(raw):
    cfg, series, params, rng = setup(raw)
    nxt, last = dict(series.first_number), {}
    record_given(series, "PENTA", "PENTA-1", 1042, nxt, last)
    doses = offer(cfg, series, params, rng, 1042 + 20, 1000, nxt, last)
    assert "PENTA-2" not in doses
    doses = offer(cfg, series, params, rng, 1042 + 28, 1000, nxt, last)
    assert "PENTA-2" in doses


def test_rota_closes_after_max_age(raw):
    cfg, series, params, rng = setup(raw)
    nxt, last = dict(series.first_number), {}
    offer(cfg, series, params, rng, 1000 + 200, 1000, nxt, last)
    assert nxt["ROTA"] == CLOSED


def test_missed_opportunity_is_offered_again(raw):
    cfg, series, params, _ = setup(raw)
    params.give_prob["MR-1"] = 0.0
    nxt, last = dict(series.first_number), {}
    assert "MR-1" not in offer(cfg, series, params, np.random.default_rng(1), 1000 + 280, 1000, nxt, last)
    params.give_prob["MR-1"] = 1.0
    assert "MR-1" in offer(cfg, series, params, np.random.default_rng(1), 1000 + 310, 1000, nxt, last)
