"""Command line: `immdss simulate`, `immdss validate-sim` and `immdss eda`."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from .eda import run_eda
from .forecast.commands import (
    build_series,
    evaluate_alerts,
    run_alert_study,
    run_backtests,
    train_final,
)
from .forecast.guard import TrainingRefused
from .sim.calibrate import calibrate, refine
from .sim.config import ConfigError, load_config, parse_config
from .sim.dirty import build_dirty_imports
from .sim.engine import Engine
from .sim.outputs import reusable_run, write_run
from .sim.validate import coverage_table, validate_run, write_report

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "sim.yaml"


def simulate(config: Path, out: Path, seed: int | None, force: bool = False) -> tuple[Path, bool]:
    """Returns (run directory, whether it was generated now)."""
    cfg = load_config(config, seed)
    existing = None if force else reusable_run(out, cfg)
    if existing:
        print(f"up to date: {existing} (same seed, config and generator code; validated). --force to rebuild")
        return existing, False
    t0 = time.perf_counter()
    rngs = [np.random.default_rng(s) for s in np.random.SeedSequence([cfg.seed, 1]).spawn(2)]
    params, calibration = calibrate(cfg, rngs[0])
    print(
        f"calibrated in {time.perf_counter() - t0:.0f}s, max error "
        f"{max(abs(v) for v in calibration['final_error_pp'].values())} pp"
    )
    result = Engine(cfg, params).run()
    cal = cfg.section("calibration")
    max_rounds, target = int(cal.get("engine_refinements", 2)), float(cal.get("engine_target_pp", 0.0))
    for stage in range(max_rounds + 1):
        cov = coverage_table(cfg, result.tables["immunization_events"], result.truth["children_truth"])
        worst = cov.difference_pp.abs().max()
        calibration.setdefault("engine_refinement", []).append(
            {"stage": stage, "max_abs_error_pp": float(worst)}
        )
        print(f"engine refinement {stage}: max error {worst} pp")
        if worst <= target or stage == max_rounds:
            break
        params = refine(cfg, params, dict(zip(cov.indicator, cov.simulated_pct, strict=True)))
        result = Engine(cfg, params).run()
    calibration["final_params"] = params.to_dict()
    dirty_cfg = cfg.section("dirty_import")
    imports = build_dirty_imports(
        result.tables, int(dirty_cfg["rows"]), float(dirty_cfg["defect_share"]), cfg.as_of_date, rngs[1]
    )
    run_dir = write_run(
        out,
        cfg,
        {"app": result.tables, "truth": result.truth, "imports": imports},
        {"params": cfg.raw, "calibration_report": calibration},
    )
    print(f"wrote {run_dir} in {time.perf_counter() - t0:.0f}s")
    for name, frame in result.tables.items():
        print(f"  app/{name}.csv: {len(frame):,} rows")
    return run_dir, True


def validate(config: Path, run_dir: Path) -> bool:
    snapshot = run_dir / "params.json"
    cfg = parse_config(json.loads(snapshot.read_text())) if snapshot.exists() else load_config(config)
    report = validate_run(cfg, run_dir)
    write_report(report, run_dir)
    for c in report.checks:
        print(f"{c.check_id} {'PASS' if c.passed else 'FAIL'}  {c.description}: {c.detail}")
    print(f"report: {run_dir / 'validation_report.md'}")
    return report.passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="immdss")
    sub = parser.add_subparsers(dest="command", required=True)
    p_sim = sub.add_parser("simulate", help="generate a seeded synthetic dataset")
    p_sim.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p_sim.add_argument("--out", type=Path, default=Path("data/synthetic"))
    p_sim.add_argument("--seed", type=int, default=None)
    p_sim.add_argument("--no-validate", action="store_true")
    p_sim.add_argument("--force", action="store_true", help="rebuild even if an identical run exists")
    p_val = sub.add_parser("validate-sim", help="check a generated run")
    p_val.add_argument("run_dir", type=Path)
    p_val.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p_eda = sub.add_parser("eda", help="EDA figures and dataset description for a validated run")
    p_eda.add_argument("run_dir", type=Path)
    p_eda.add_argument("--out", type=Path, default=Path("docs/evidence"))
    p_series = sub.add_parser(
        "build-series", help="weekly training series from a validated run's stock ledger"
    )
    p_series.add_argument("run_dir", type=Path)
    p_series.add_argument("--out", type=Path, default=Path("data/processed"))
    p_back = sub.add_parser("backtest", help="rolling-origin backtest, comparison and selection (Colab only)")
    p_back.add_argument("run_dir", type=Path)
    p_back.add_argument("--series", type=Path, required=True)
    p_back.add_argument("--models", default="b1,b2,sarima,gru")
    p_back.add_argument("--seed", type=int, default=42)
    p_back.add_argument("--out", type=Path, required=True)
    p_final = sub.add_parser(
        "train-final", help="fit the selected model per series on all weeks (Colab only)"
    )
    p_final.add_argument("--series", type=Path, required=True)
    p_final.add_argument("--results", type=Path, required=True)
    p_final.add_argument("--seed", type=int, default=42)
    p_alerts = sub.add_parser(
        "evaluate-alerts", help="stock-out alert precision and recall against ground truth for a backtest"
    )
    p_alerts.add_argument("run_dir", type=Path)
    p_alerts.add_argument("--results", type=Path, required=True)
    p_study = sub.add_parser(
        "alert-study",
        help="weekly alert decisions, delivery-history gate and risk score against ground truth",
    )
    p_study.add_argument("run_dir", type=Path)
    p_study.add_argument("--series", type=Path, required=True)
    p_study.add_argument("--results", type=Path, required=True, help="backtest folder with selection.csv")
    p_study.add_argument("--seed", type=int, default=42)
    p_study.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "simulate":
            run_dir, generated = simulate(args.config, args.out, args.seed, args.force)
            if generated and not args.no_validate:
                return 0 if validate(args.config, run_dir) else 1
            return 0
        if args.command == "build-series":
            build_series(args.run_dir, args.out)
            return 0
        if args.command == "backtest":
            run_backtests(args.run_dir, args.series, args.models.split(","), args.seed, args.out)
            return 0
        if args.command == "alert-study":
            run_alert_study(args.run_dir, args.series, args.results, args.seed, args.out)
            return 0
        if args.command == "evaluate-alerts":
            evaluate_alerts(args.run_dir, args.results)
            return 0
        if args.command == "train-final":
            train_final(args.series, args.results, args.seed)
            return 0
        if args.command == "eda":
            print(f"report: {run_eda(args.run_dir, args.out)}")
            return 0
        return 0 if validate(args.config, args.run_dir) else 1
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    except TrainingRefused as exc:
        print(exc, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
