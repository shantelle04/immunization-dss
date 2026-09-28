"""EDA evidence: refuses unvalidated runs; produces every figure and T-5.1 for the validated evidence run."""

from pathlib import Path

import pytest
from test_simulation import generate

from immdss_analytics.eda import FIGURES, run_eda
from immdss_analytics.sim.validate import validate_run, write_report

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_RUN = (
    ROOT / "data" / "synthetic" / (ROOT / "analytics" / "configs" / "evidence_run.txt").read_text().strip()
)


def test_eda_refuses_a_run_that_failed_validation(small_cfg, tmp_path):
    _, run_dir = generate(small_cfg, tmp_path / "run")
    report = validate_run(small_cfg, run_dir)
    write_report(report, run_dir)
    assert not report.passed, "small config is expected to miss the KDHS tolerance (V-10)"
    with pytest.raises(ValueError, match="did not pass validate-sim"):
        run_eda(run_dir, tmp_path / "out")


@pytest.mark.skipif(not EVIDENCE_RUN.exists(), reason="evidence run not generated on this machine")
def test_eda_writes_every_figure_and_the_dataset_table(tmp_path):
    report = run_eda(EVIDENCE_RUN, tmp_path)
    pngs = sorted(p.name.split("_")[0] for p in tmp_path.glob("F-D*.png"))
    assert pngs == [f"F-D{i}" for i in range(1, len(FIGURES) + 1)]
    text = report.read_text()
    assert "## T-5.1 Dataset description" in text
    assert "truth | weekly_stock.csv | 21,840" in text
    assert "Evaluation only, never loaded" in text
