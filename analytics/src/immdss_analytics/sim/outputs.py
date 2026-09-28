"""Write a simulator run to disk with a manifest of hashes and row counts."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from .. import __version__
from .config import SimConfig

LAYOUT = {
    "app": "Tables the system ingests (the only files loaded into the application database)",
    "truth": "Ground truth for evaluation only; never loaded into the application",
    "imports": "CSV import samples with planted defects and their answer key",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"


def code_sha256() -> str:
    """Hash of the generator source: the run ID covers seed and config, not code changes."""
    h = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        h.update(path.name.encode())
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def reusable_run(out_root: Path, cfg: SimConfig) -> Path | None:
    """An existing run with the same seed, config and generator code that passed validation."""
    run_dir = out_root / run_id(cfg)
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text())
        passed = json.loads((run_dir / "validation_report.json").read_text())["passed"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None
    same = manifest.get("config_sha256") == cfg.config_hash and manifest.get("code_sha256") == code_sha256()
    return run_dir if same and passed else None


def run_id(cfg: SimConfig) -> str:
    return f"sim-seed{cfg.seed}-{cfg.config_hash[:8]}"


def write_run(
    out_root: Path, cfg: SimConfig, groups: dict[str, dict[str, pd.DataFrame]], extra_json: dict[str, dict]
) -> Path:
    run_dir = out_root / run_id(cfg)
    files = {}
    for group, tables in groups.items():
        (run_dir / group).mkdir(parents=True, exist_ok=True)
        for name, frame in tables.items():
            path = run_dir / group / f"{name}.csv"
            frame.to_csv(path, index=False, lineterminator="\n")
            files[f"{group}/{name}.csv"] = {"rows": len(frame), "sha256": sha256(path)}
    for name, payload in extra_json.items():
        path = run_dir / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        files[f"{name}.json"] = {"sha256": sha256(path)}
    manifest = {
        "run_id": run_id(cfg),
        "seed": cfg.seed,
        "config_sha256": cfg.config_hash,
        "code_sha256": code_sha256(),
        "package_version": __version__,
        "git_commit": _git_sha(),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "window": {
            "history_from": cfg.sim_start.isoformat(),
            "stock_from": cfg.start_date.isoformat(),
            "end": cfg.end_date.isoformat(),
            "as_of": cfg.as_of_date.isoformat(),
        },
        "layout": LAYOUT,
        "synthetic": True,
        "files": files,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return run_dir
