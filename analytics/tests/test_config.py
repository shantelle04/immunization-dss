import pytest

from immdss_analytics.sim.config import ConfigError, parse_config


def test_default_config_is_valid(raw):
    cfg = parse_config(raw)
    assert len(cfg.facilities) == 12
    assert cfg.dose_rules["PENTA-3"].target_key == "penta3"
    assert cfg.dose_rules["BCG-1"].target_key == "bcg"
    assert [c.name for c in cfg.contacts] == ["birth", "w6", "w10", "w14", "m9", "m18"]


def test_every_violation_is_reported_at_once(raw):
    raw["start_date"] = "2021-01-05"
    raw["facilities"][0]["births_per_week"] = 0
    raw["antigens"]["BCG"]["doses_per_vial"] = 0
    raw["stock"]["delivery_skip_probability"] = 1.5
    with pytest.raises(ConfigError) as err:
        parse_config(raw)
    message = str(err.value)
    for fragment in (
        "start_date: must be a Monday",
        "births_per_week: must be > 0",
        "antigens.BCG.doses_per_vial",
        "stock.delivery_skip_probability",
    ):
        assert fragment in message


def test_missing_section_fails_loudly(raw):
    del raw["stock"]
    with pytest.raises(ConfigError, match="missing sections: stock"):
        parse_config(raw)


def test_unknown_dose_in_contact_is_rejected(raw):
    raw["contacts"]["w6"]["doses"].append("HPV-1")
    with pytest.raises(ConfigError, match="unknown dose HPV-1"):
        parse_config(raw)


def test_subgroup_categories_must_match_population(raw):
    del raw["calibration"]["penta3_by_group"]["wealth"]["lowest"]
    with pytest.raises(ConfigError, match="penta3_by_group.wealth"):
        parse_config(raw)


def test_batching_day_must_be_a_static_day_at_each_level(raw):
    raw["sessions"]["batching"]["weekday"] = 0
    raw["sessions"]["batching"]["levels_by_antigen"]["HPV"] = ["dispensary"]
    with pytest.raises(ConfigError) as err:
        parse_config(raw)
    assert "not a static day at level 'dispensary'" in str(err.value)
    assert "sessions.batching.levels_by_antigen: unknown antigen 'HPV'" in str(err.value)


def test_config_hash_changes_with_content(raw):
    a = parse_config(raw).config_hash
    raw["seed"] = 7
    assert parse_config(raw).config_hash != a
