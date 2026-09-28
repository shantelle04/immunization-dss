from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from immdss_analytics.sim.config import SimConfig, parse_config

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "sim.yaml"


@pytest.fixture(scope="session")
def base_raw() -> dict:
    return yaml.safe_load(CONFIG.read_text())


@pytest.fixture
def raw(base_raw: dict) -> dict:
    return copy.deepcopy(base_raw)


def small_raw(base_raw: dict) -> dict:
    """Three facilities, 60 weeks of stock, small calibration cohort: fast but exercises every path."""
    r = copy.deepcopy(base_raw)
    r["facilities"] = r["facilities"][:1] + r["facilities"][5:6] + r["facilities"][9:10]
    r["weeks"] = 60
    r["warmup_weeks"] = 80
    r["as_of_date"] = "2022-02-21"
    r["calibration"]["cohort_size"] = 3000
    r["calibration"]["iterations"] = 6
    r["calibration"]["engine_refinements"] = 0
    r["stock"]["disruptions"] = [{"antigen": "OPV", "start_week": 10, "weeks": 6, "fill_rate": 0.0}]
    r["dirty_import"]["rows"] = 120
    return r


@pytest.fixture(scope="session")
def small_cfg(base_raw: dict) -> SimConfig:
    return parse_config(small_raw(base_raw))
