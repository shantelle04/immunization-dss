"""End-to-end runs on a small configuration: consistency checks, reproducibility, dirty imports."""

import json

import numpy as np
import pytest

from immdss_analytics.sim.calibrate import calibrate
from immdss_analytics.sim.dirty import build_dirty_imports
from immdss_analytics.sim.engine import Engine
from immdss_analytics.sim.outputs import write_run
from immdss_analytics.sim.validate import validate_run


def generate(cfg, out):
    params, report = calibrate(cfg, np.random.default_rng(cfg.seed))
    result = Engine(cfg, params).run()
    imports = build_dirty_imports(
        result.tables,
        cfg.section("dirty_import")["rows"],
        cfg.section("dirty_import")["defect_share"],
        cfg.as_of_date,
        np.random.default_rng(1),
    )
    run_dir = write_run(
        out,
        cfg,
        {"app": result.tables, "truth": result.truth, "imports": imports},
        {"params": cfg.raw, "calibration_report": report},
    )
    return result, run_dir


@pytest.fixture(scope="module")
def run(small_cfg, tmp_path_factory):
    return generate(small_cfg, tmp_path_factory.mktemp("a"))


def test_consistency_checks_pass(small_cfg, run):
    _, run_dir = run
    report = validate_run(small_cfg, run_dir)
    failed = {c.check_id: c.detail for c in report.checks if not c.passed and c.check_id != "V-10"}
    assert failed == {}


def test_same_seed_reproduces_identical_files(small_cfg, run, tmp_path):
    _, first = run
    _, second = generate(small_cfg, tmp_path)
    a = json.loads((first / "manifest.json").read_text())["files"]
    b = json.loads((second / "manifest.json").read_text())["files"]
    assert a == b


def test_app_tables_hold_no_ground_truth(run):
    result, _ = run
    for name in ("education", "wealth", "risk_log_odds", "dropout_after_contact"):
        for table in result.tables.values():
            assert name not in table.columns
    assert result.tables["children"].is_synthetic.all()


def test_disruption_causes_stockouts_in_window(small_cfg, run):
    result, _ = run
    w = result.truth["weekly_stock"]
    opv = w[(w.antigen_code == "OPV") & (w.week_start >= small_cfg.start_date.isoformat())]
    assert opv[opv.in_disruption].stockout.any()


def test_batched_antigens_only_on_batch_day_at_static_sessions(small_cfg, run):
    import pandas as pd

    result, _ = run
    batching = small_cfg.section("sessions")["batching"]
    level_of = {f.code: f.level for f in small_cfg.facilities}
    ev = result.tables["immunization_events"].merge(
        result.tables["sessions"][["session_id", "kind"]], on="session_id"
    )
    ev = ev[ev.kind == "fixed"]
    rules = batching["levels_by_antigen"]
    batched = [
        level_of[fac] in rules.get(ag, []) for fac, ag in zip(ev.facility_code, ev.antigen_code, strict=True)
    ]
    weekday = pd.to_datetime(ev.given_on).dt.weekday
    assert any(batched)
    assert (weekday[batched] == batching["weekday"]).all()
    assert (weekday[[not b for b in batched]] != batching["weekday"]).any()
    hospital_mr = ev[(ev.antigen_code == "MR") & ev.facility_code.map(level_of).eq("sub_county_hospital")]
    assert (pd.to_datetime(hospital_mr.given_on).dt.weekday != batching["weekday"]).any(), (
        "MR not batched there"
    )


def test_reusable_run_requires_same_code_config_and_passed_validation(small_cfg, tmp_path, monkeypatch):
    from immdss_analytics.sim import outputs

    _, run_dir = generate(small_cfg, tmp_path)
    assert outputs.reusable_run(tmp_path, small_cfg) is None, "no validation report yet"
    (run_dir / "validation_report.json").write_text(json.dumps({"passed": False}))
    assert outputs.reusable_run(tmp_path, small_cfg) is None, "failed validation is never reused"
    (run_dir / "validation_report.json").write_text(json.dumps({"passed": True}))
    assert outputs.reusable_run(tmp_path, small_cfg) == run_dir
    monkeypatch.setattr(outputs, "code_sha256", lambda: "changed-generator")
    assert outputs.reusable_run(tmp_path, small_cfg) is None, "a code change forces regeneration"


def test_registry_excludes_zero_dose_children(run):
    result, _ = run
    truth = result.truth["children_truth"]
    never = truth[~truth.entered_care].child_id
    assert not result.tables["children"].child_id.isin(never).any()


def test_dirty_import_answer_key_matches_files(run):
    _, run_dir = run
    import pandas as pd

    key = pd.read_csv(run_dir / "imports" / "import_dirty_truth.csv")
    imm = pd.read_csv(run_dir / "imports" / "import_immunizations_dirty.csv", keep_default_na=False)
    assert len(key) > 0
    assert key[key.file == "immunizations"].row_index.max() < len(imm)
    missing = key[(key.file == "immunizations") & (key.defect == "MISSING_CHILD_ID")].row_index
    assert (imm.loc[missing, "child_system_id"] == "").all()
