"""Cross-platform task runner (Linux, macOS, Windows). Standard library only.

Usage: python scripts/dev.py <command> [args]   (Windows: py scripts\\dev.py <command>)

Every result-producing command (simulate, validate, eda, test, lint, check) appends one line to
docs/logs/results_ledger.jsonl when docs/logs exists; `history` renders it as a markdown table.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
BIN = VENV / ("Scripts" if os.name == "nt" else "bin")
PY = BIN / ("python.exe" if os.name == "nt" else "python")
# The run cited in the thesis; one tracked file so the runner and tests agree.
DEFAULT_RUN = f"data/synthetic/{(ROOT / 'analytics' / 'configs' / 'evidence_run.txt').read_text().strip()}"
LEDGER = ROOT / "docs" / "logs" / "results_ledger.jsonl"
HISTORY = ROOT / "docs" / "logs" / "RESULTS_HISTORY.md"
PLACEHOLDER = "changeme"
SECRET_BYTES = {"DJANGO_SECRET_KEY": 64}
# Numeric libraries otherwise start one thread per core; the simulator is single-threaded by design.
ONE_THREAD = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
# Pinned by digest so every render uses the same PlantUML (1.2026.8).
PLANTUML_IMAGE = "plantuml/plantuml@sha256:d08610df482510844382caa4e016ba2bf7e3231f630f02ee12f250f3416c62b1"


@dataclass
class Result:
    code: int
    output: str
    seconds: float


def _low_priority() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS}
    return {"preexec_fn": lambda: os.nice(10)}


def run(
    *cmd: str | Path,
    cwd: Path = ROOT,
    heavy: bool = False,
    exit_on_error: bool = True,
    extra_env: dict | None = None,
) -> Result:
    """Run a command, echo its output live, and keep a copy for the ledger."""
    print("$", " ".join(str(c) for c in cmd), flush=True)
    env = {**os.environ, **(ONE_THREAD if heavy else {}), **(extra_env or {})} if heavy or extra_env else None
    start = time.perf_counter()
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        **(_low_priority() if heavy else {}),
    )
    lines = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    code = proc.wait()
    result = Result(code, "".join(lines), round(time.perf_counter() - start, 1))
    if code != 0 and exit_on_error:
        sys.exit(code)
    return result


def tool(name: str) -> Path:
    return BIN / (f"{name}.exe" if os.name == "nt" else name)


def npm() -> str:
    found = shutil.which("npm")
    if not found:
        sys.exit("npm not found: install Node.js 20 or 22")
    return found


# ------------------------------------------------------------------ ledger
def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"


def _peak_child_mb() -> float | None:
    try:
        import resource
    except ImportError:
        return None
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(rss / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


def record(command: str, results: list[Result], details: dict, ledger: Path = LEDGER) -> None:
    if not ledger.parent.is_dir():
        print(f"ledger: {ledger.parent} not found, result not recorded")
        return
    code = max((r.code for r in results), default=0)
    entry = {
        "at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "command": command,
        "outcome": "PASS" if code == 0 else "FAIL",
        "exit_code": code,
        "seconds": round(sum(r.seconds for r in results), 1),
        "peak_child_rss_mb": _peak_child_mb(),
        "git_commit": _git_commit(),
        "details": details,
    }
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"ledger: {command} {entry['outcome']} recorded in {ledger}")


def run_summary(run_dir: Path) -> dict:
    """Headline numbers of a generated run, read from its own manifest and validation report."""
    manifest = json.loads((run_dir / "manifest.json").read_text())
    summary = {
        "run_id": manifest["run_id"],
        "seed": manifest["seed"],
        "config": manifest["config_sha256"][:8],
        "rows": {k: v["rows"] for k, v in manifest["files"].items() if k.startswith("app/")},
    }
    report_path = run_dir / "validation_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        coverage = report["tables"]["coverage_vs_kdhs2022"]
        worst = max(coverage, key=lambda r: abs(r["difference_pp"]))
        summary["validation"] = "PASS" if report["passed"] else "FAIL"
        summary["checks_passed"] = f"{sum(c['passed'] for c in report['checks'])}/{len(report['checks'])}"
        summary["max_coverage_diff_pp"] = f"{worst['difference_pp']} ({worst['indicator']})"
        summary["wastage_who_pct"] = {
            r["antigen_code"]: r.get("wastage_rate_who_pct") for r in report["tables"]["stock_summary"]
        }
    return summary


def _run_dir_from(output: str) -> Path | None:
    match = re.search(r"(?:wrote|up to date:) (\S+)", output)
    return Path(match.group(1)) if match else None


# ---------------------------------------------------------------- commands
def setup(_: argparse.Namespace) -> None:
    if not PY.exists():
        run(sys.executable, "-m", "venv", VENV)
    run(PY, "-m", "pip", "install", "-r", "requirements.txt")
    run(npm(), "ci", cwd=ROOT / "frontend")
    run("git", "config", "--local", "core.hooksPath", "scripts/hooks")
    if not (ROOT / ".env").exists():
        print("next: python scripts/dev.py env   (creates .env with generated secrets)")


def generate_env(example: Path, target: Path) -> list[str]:
    """Write `target` from `example`, replacing every placeholder with a random secret.

    Returns the names of generated variables; values are never printed.
    """
    if target.exists():
        raise FileExistsError(f"{target.name} already exists; delete it first (then run db-reset)")
    generated, lines = [], []
    for line in example.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#") and value.startswith(PLACEHOLDER):
            value = secrets.token_urlsafe(SECRET_BYTES.get(key, 32))
            generated.append(key)
        lines.append(f"{key}{sep}{value}" if sep else line)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return generated


def env(_: argparse.Namespace) -> None:
    try:
        names = generate_env(ROOT / ".env.example", ROOT / ".env")
    except FileExistsError as exc:
        sys.exit(f"env: {exc}")
    print(f"env: wrote .env (owner read/write only) with generated values for: {', '.join(names)}")


def db_up(_: argparse.Namespace) -> None:
    run("docker", "compose", "up", "-d", "--wait", "db")


def db_down(_: argparse.Namespace) -> None:
    run("docker", "compose", "down")


def db_reset(_: argparse.Namespace) -> None:
    if input("Delete the local database volume and all its data? Type yes: ").strip() != "yes":
        sys.exit("aborted")
    run("docker", "compose", "down", "-v")


def db_shell(_: argparse.Namespace) -> None:
    run("docker", "compose", "exec", "db", "bash", "-c", 'psql -U "$DB_USER" -d "$DB_NAME"')


def check(_: argparse.Namespace) -> None:
    result = run(PY, "manage.py", "check", cwd=ROOT / "backend", exit_on_error=False)
    record("check", [result], {"django_check": result.output.strip().splitlines()[-1:]})
    if result.code:
        sys.exit(result.code)


def _test_summary(output: str) -> str:
    lines = [ln.strip() for ln in output.splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    return lines[-1] if lines else "no summary"


def test(args: argparse.Namespace) -> None:
    parts = {
        "analytics": lambda: run(tool("pytest"), "analytics", "-q", heavy=True, exit_on_error=False),
        "scripts": lambda: run(tool("pytest"), "scripts", "-q", exit_on_error=False),
        "backend": lambda: run(tool("pytest"), "-q", cwd=ROOT / "backend", exit_on_error=False),
        "frontend": lambda: run(npm(), "test", cwd=ROOT / "frontend", exit_on_error=False),
    }
    chosen = list(parts) if args.part == "all" else [args.part]
    results, details = [], {}
    for name in chosen:
        result = parts[name]()
        results.append(result)
        details[name] = _test_summary(result.output)
    record(f"test {args.part}", results, details)
    if any(r.code for r in results):
        sys.exit(1)


def lint(_: argparse.Namespace) -> None:
    results, details = [], {}
    for target in ("analytics", "backend", "scripts"):
        for sub in (["check"], ["format", "--check"]):
            result = run(tool("ruff"), *sub, target, exit_on_error=False)
            results.append(result)
            details[f"{target} {sub[0]}"] = "clean" if result.code == 0 else "issues"
    record("lint", results, details)
    if any(r.code for r in results):
        sys.exit(1)


def simulate(args: argparse.Namespace) -> None:
    cmd = [tool("immdss"), "simulate", "--out", "data/synthetic"] + (["--force"] if args.force else [])
    result = run(*cmd, heavy=True, exit_on_error=False)
    run_dir = _run_dir_from(result.output)
    details = run_summary(ROOT / run_dir) if run_dir else {}
    details["reused_existing_run"] = "up to date:" in result.output
    record("simulate", [result], details)
    if result.code:
        sys.exit(result.code)


def validate(args: argparse.Namespace) -> None:
    result = run(tool("immdss"), "validate-sim", args.run, heavy=True, exit_on_error=False)
    record("validate", [result], run_summary(ROOT / args.run))
    if result.code:
        sys.exit(result.code)


def eda(args: argparse.Namespace) -> None:
    result = run(tool("immdss"), "eda", args.run, "--out", "docs/evidence", heavy=True, exit_on_error=False)
    figures = sorted(p.name for p in (ROOT / "docs" / "evidence").glob("F-D*.png"))
    record("eda", [result], {"run_id": Path(args.run).name, "figures": len(figures)})
    if result.code:
        sys.exit(result.code)


def diagrams(_: argparse.Namespace) -> None:
    """Render docs/diagrams/*.puml to SVG and 200-dpi PNG in docs/evidence (memory-capped container)."""
    generator = ROOT / "docs" / "diagrams" / "gen_schema.py"
    if generator.exists():
        run(PY, generator)
    sources = sorted(p.name for p in (ROOT / "docs" / "diagrams").glob("*.puml"))
    user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []
    base = ["docker", "run", "--rm", "--memory=768m", "-e", "JAVA_TOOL_OPTIONS=-Xmx512m", *user]
    # PlantUML crops PNGs wider or taller than 4096 px by default; large diagrams at 200 dpi exceed that.
    base += ["-e", "PLANTUML_LIMIT_SIZE=16384"]
    base += ["-v", f"{ROOT / 'docs'}:/docs", "-w", "/docs/diagrams", PLANTUML_IMAGE, "-failfast2"]
    results = [
        run(*base, "-tsvg", "-o", "/docs/evidence", *sources, heavy=True, exit_on_error=False),
        run(*base, "-tpng", "-Sdpi=200", "-o", "/docs/evidence", *sources, heavy=True, exit_on_error=False),
    ]
    record("diagrams", results, {"sources": len(sources), "files": sources})
    if any(r.code for r in results):
        sys.exit(1)


def _clinical_env() -> dict:
    """IMMDSS_TODAY from the environment, else the evidence run's as-of date (D-32)."""
    if os.environ.get("IMMDSS_TODAY"):
        return {}
    manifest = ROOT / DEFAULT_RUN / "manifest.json"
    if not manifest.exists():
        return {}
    return {"IMMDSS_TODAY": json.loads(manifest.read_text())["window"]["as_of"]}


def load(args: argparse.Namespace) -> None:
    cmd = [PY, "manage.py", "load_synthetic", ROOT / args.run] + (["--replace"] if args.replace else [])
    result = run(*cmd, cwd=ROOT / "backend", heavy=True, exit_on_error=False)
    counts = dict(line.split(": ", 1) for line in result.output.splitlines() if ": " in line)
    record("load", [result], counts)
    if result.code:
        sys.exit(result.code)


def demo_users(args: argparse.Namespace) -> None:
    cmd = [PY, "manage.py", "seed_demo_users"] + (["--reset"] if args.reset else [])
    result = run(*cmd, cwd=ROOT / "backend", exit_on_error=False)
    record("demo-users", [result], {"summary": result.output.strip().splitlines()[-1:]})
    if result.code:
        sys.exit(result.code)


def walkthrough(args: argparse.Namespace) -> None:
    out = ROOT / "docs" / "evidence" / f"P{args.prototype}_walkthrough_{Path(args.run).name}.md"
    result = run(
        PY,
        "-m",
        "evaluation.walkthrough",
        ROOT / args.run,
        "--out",
        out,
        cwd=ROOT / "backend",
        heavy=True,
        exit_on_error=False,
        extra_env=_clinical_env(),
    )
    details: dict = {"report": out.name}
    if result.code == 0:
        data = json.loads(result.output[result.output.index("{") :])
        details["max_p95_ms"] = max(r["p95_ms"] for r in data["latency"])
        details["accuracy_pct"] = {r["query"]: r["accuracy_pct"] for r in data["accuracy"]}
        planted = [r for r in data["ingestion"] if not r["defect"].startswith("(")]
        clean = [r for r in data["ingestion"] if r["defect"].startswith("(")]
        for label, rows in (("defects_caught", planted), ("clean_rows_rejected", clean)):
            details[label] = f"{sum(r['caught_any'] for r in rows)}/{sum(r['planted'] for r in rows)}"
    record("walkthrough", [result], details)
    if result.code:
        sys.exit(result.code)


def forecasts(args: argparse.Namespace) -> None:
    """Store 4-week forecasts and refresh alerts: baselines, or the results folder of a Colab run."""
    cmd = [PY, "manage.py", "run_forecasts"] + (["--results", ROOT / args.results] if args.results else [])
    result = run(*cmd, cwd=ROOT / "backend", heavy=True, exit_on_error=False, extra_env=_clinical_env())
    details: dict = {"seconds": round(result.seconds, 1)}
    if result.code == 0:
        data = json.loads(result.output[result.output.index("{") :])
        keys = ("source", "series", "weeks", "models", "forecasts", "alerts_active", "data_sha256")
        details.update({k: data.get(k) for k in keys})
    record("forecasts", [result], details)
    if result.code:
        sys.exit(result.code)


def evaluate_models(args: argparse.Namespace) -> None:
    """Baseline backtest and stock-out alert evaluation against ground truth (no model is fitted)."""
    run_dir = ROOT / args.run
    out = ROOT / "data" / "results" / f"{run_dir.name}-baselines"
    steps = [
        run(
            tool("immdss"), "build-series", run_dir, "--out", ROOT / "data" / "processed", exit_on_error=False
        ),
        run(
            tool("immdss"),
            "backtest",
            run_dir,
            "--series",
            ROOT / "data" / "processed" / run_dir.name / "weekly_issues.csv",
            "--models",
            "b1,b2",
            "--out",
            out,
            heavy=True,
            exit_on_error=False,
        ),
        run(tool("immdss"), "evaluate-alerts", run_dir, "--results", out, exit_on_error=False),
        run(
            tool("immdss"),
            "alert-study",
            run_dir,
            "--series",
            ROOT / "data" / "processed" / run_dir.name / "weekly_issues.csv",
            "--results",
            out,
            "--out",
            out / "alert_study",
            heavy=True,
            exit_on_error=False,
        ),
    ]
    details: dict = {"results": str(out.relative_to(ROOT))}
    if all(r.code == 0 for r in steps):
        manifest = json.loads((out / "manifest.json").read_text())
        alerts = json.loads((out / "alert_metrics.json").read_text())
        details["series_sha256"] = manifest["series_sha256"]
        details["backtest"] = {
            r["model"]: {k: r[k] for k in ("mean_mase", "mean_mae", "mean_smape", "coverage80")}
            for r in manifest["overall"]
        }
        details["alerts"] = {
            k: alerts[k] for k in ("alerts", "true_stockout_weeks", "recall", "precision", "f1", "buffer")
        }
        details["alert_sensitivity"] = alerts["sensitivity"]
        study = json.loads((out / "alert_study" / "manifest.json").read_text())
        keep = ("method", "flagged_share", "recall", "early_recall", "onset_early_recall", "lift")
        details["alert_study_weekly"] = [{k: r[k] for k in keep} for r in study["results"]]
    record("evaluate", steps, details)
    if any(r.code for r in steps):
        sys.exit(1)


def _wait_for(url: str, seconds: int = 60) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True
        except OSError:
            time.sleep(0.5)
    return False


def e2e(args: argparse.Namespace) -> None:
    """Browser tests (Playwright, installed Chrome) against a separate database with its own accounts."""
    password = secrets.token_urlsafe(24)
    shots = ROOT / "docs" / "evidence"
    backend_env = {
        **os.environ,
        **_clinical_env(),
        "DJANGO_SETTINGS_MODULE": "config.settings_e2e",
        "IMMDSS_E2E_PASSWORD": password,
        "DJANGO_CORS_ORIGINS": "http://localhost:5174,http://127.0.0.1:5174",
    }
    prepare = run(
        PY,
        "-m",
        "evaluation.e2e_prepare",
        ROOT / args.run,
        cwd=ROOT / "backend",
        heavy=True,
        exit_on_error=False,
        extra_env=backend_env,
    )
    if prepare.code:
        record("e2e", [prepare], {"stage": "prepare"})
        sys.exit(prepare.code)
    group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    servers = [
        subprocess.Popen(
            [str(PY), "manage.py", "runserver", "127.0.0.1:8001", "--noreload"],
            cwd=ROOT / "backend",
            env=backend_env,
            **group,
            **quiet,
        ),
        subprocess.Popen(
            [npm(), "run", "dev"],
            cwd=ROOT / "frontend",
            env={**os.environ, "IMMDSS_API": "http://127.0.0.1:8001", "IMMDSS_WEB_PORT": "5174"},
            **group,
            **quiet,
        ),
    ]
    try:
        up = _wait_for("http://127.0.0.1:8001/api/v1/auth/me") and _wait_for("http://localhost:5174/")
        if not up:
            sys.exit("e2e: the test servers did not start (are ports 8001 and 5174 free?)")
        result = run(
            "npx",
            "playwright",
            "test",
            cwd=ROOT / "frontend",
            exit_on_error=False,
            extra_env={
                "E2E_PASSWORD": password,
                "E2E_BASE_URL": "http://localhost:5174",
                "E2E_SHOTS": str(shots) if args.screenshots else "",
            },
        )
    finally:
        for proc in servers:
            _stop_tree(proc)
    summary = [ln.strip() for ln in result.output.splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    record("e2e", [prepare, result], {"summary": summary, "screenshots": bool(args.screenshots)})
    if result.code:
        sys.exit(result.code)


def run_app(_: argparse.Namespace) -> None:
    """Backend on 127.0.0.1:8000 and the frontend on http://localhost:5173 (API proxied); Ctrl+C stops."""
    env = {**os.environ, **_clinical_env()}
    # Each server gets its own process group so stopping it also stops children (npm starts vite).
    if os.name == "nt":
        group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        group = {"start_new_session": True}
    server = [str(PY), "manage.py", "runserver", "127.0.0.1:8000"]
    backend = subprocess.Popen(server, cwd=ROOT / "backend", env=env, **group)
    frontend = subprocess.Popen([npm(), "run", "dev"], cwd=ROOT / "frontend", env=env, **group)
    print("\nOpen http://localhost:5173  (Ctrl+C to stop)\n", flush=True)
    signal.signal(signal.SIGTERM, _interrupt)  # a plain kill also stops both servers
    try:
        backend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (frontend, backend):
            _stop_tree(proc)


def _interrupt(*_: object) -> None:
    raise KeyboardInterrupt


def _stop_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    proc.wait()


def bootstrap(args: argparse.Namespace) -> None:
    if not (ROOT / ".env").exists():
        env(args)
    db_up(args)
    check(args)
    args.part = "all"
    test(args)


def history(_: argparse.Namespace) -> None:
    if not LEDGER.exists():
        sys.exit(f"history: {LEDGER.relative_to(ROOT)} does not exist yet")
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = [
        "# Results history",
        "",
        f"Generated by `scripts/dev.py history` from `results_ledger.jsonl` ({len(rows)} entries). "
        "Do not edit; the ledger is the record.",
        "",
        "| When (UTC) | Command | Outcome | Seconds | Peak RSS MB | Commit | Details |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        details = "; ".join(f"{k}: {v}" for k, v in r["details"].items() if k != "rows")
        lines.append(
            f"| {r['at']} | {r['command']} | {r['outcome']} | {r['seconds']} | "
            f"{r['peak_child_rss_mb']} | {r['git_commit']} | {details.replace('|', '/')} |"
        )
    HISTORY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"history: wrote {HISTORY.relative_to(ROOT)} ({len(rows)} entries)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="dev.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func, doc in [
        ("setup", setup, "create .venv, install pinned Python and npm packages"),
        ("env", env, "create .env from .env.example with generated secrets (never overwrites)"),
        ("bootstrap", bootstrap, "env (if missing), db-up, check, test: first run on a new machine"),
        ("db-up", db_up, "start PostgreSQL 16 in Docker and wait until healthy"),
        ("db-down", db_down, "stop the database container (data is kept)"),
        ("db-reset", db_reset, "delete the database volume (asks first)"),
        ("db-shell", db_shell, "psql inside the container as the app role"),
        ("check", check, "Django system check (runs the settings preflight)"),
        ("lint", lint, "ruff check and format check"),
        ("history", history, "render docs/logs/results_ledger.jsonl as RESULTS_HISTORY.md"),
        ("diagrams", diagrams, "render docs/diagrams/*.puml to SVG and PNG (PlantUML in Docker)"),
        ("run", run_app, "start backend and frontend: http://localhost:5173"),
    ]:
        sub.add_parser(name, help=doc).set_defaults(func=func)
    p_sim = sub.add_parser(
        "simulate", help="generate the dataset; skipped if an identical validated run exists"
    )
    p_sim.add_argument("--force", action="store_true", help="rebuild even if an identical run exists")
    p_sim.set_defaults(func=simulate)
    p_test = sub.add_parser("test", help="run tests: all, analytics, scripts, backend or frontend")
    p_test.add_argument(
        "part", nargs="?", default="all", choices=["all", "analytics", "scripts", "backend", "frontend"]
    )
    p_test.set_defaults(func=test)
    p_load = sub.add_parser("load", help="load the evidence run's app/ folder into the database")
    p_load.add_argument("run", nargs="?", default=DEFAULT_RUN)
    p_load.add_argument("--replace", action="store_true", help="replace previously loaded synthetic data")
    p_load.set_defaults(func=load)
    p_users = sub.add_parser("demo-users", help="create demo accounts; passwords go to .demo_credentials.txt")
    p_users.add_argument("--reset", action="store_true", help="give existing demo users new passwords")
    p_users.set_defaults(func=demo_users)
    p_e2e = sub.add_parser("e2e", help="browser tests on a separate database (needs Chrome and the db)")
    p_e2e.add_argument("run", nargs="?", default=DEFAULT_RUN)
    p_e2e.add_argument("--screenshots", action="store_true", help="save F-UI-*.png to docs/evidence")
    p_e2e.set_defaults(func=e2e)
    p_fc = sub.add_parser("forecasts", help="store forecasts and refresh stock-out alerts in the database")
    p_fc.add_argument("--results", help="results folder of a Colab training run; default: baselines only")
    p_fc.set_defaults(func=forecasts)
    for name, func, doc in [
        ("validate", validate, "validate a run"),
        ("eda", eda, "EDA figures for a run"),
        ("walkthrough", walkthrough, "prototype walkthrough: latency, accuracy vs truth, import cleaning"),
        ("evaluate", evaluate_models, "baseline backtest and alert precision/recall against ground truth"),
    ]:
        p = sub.add_parser(name, help=doc)
        p.add_argument("run", nargs="?", default=DEFAULT_RUN)
        if name == "walkthrough":
            p.add_argument("--prototype", type=int, default=2, help="prototype number for the report name")
        p.set_defaults(func=func)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
