"""TC-SEC-02: generated .env passes the backend startup checks; ledger records results."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from config.preflight import (  # noqa: E402
    APP_REQUIREMENTS,
    TEST_REQUIREMENTS,
    check_environment,
    credentials_distinct,
)

spec = importlib.util.spec_from_file_location("dev", ROOT / "scripts" / "dev.py")
dev = importlib.util.module_from_spec(spec)
sys.modules["dev"] = dev
spec.loader.exec_module(dev)


def parse(path: Path) -> dict[str, str]:
    pairs = (ln.split("=", 1) for ln in path.read_text().splitlines() if "=" in ln and not ln.startswith("#"))
    return dict(pairs)


def test_generated_env_passes_backend_preflight(tmp_path):
    target = tmp_path / ".env"
    names = dev.generate_env(ROOT / ".env.example", target)
    values = parse(target)
    assert set(names) == {k for k, v in parse(ROOT / ".env.example").items() if v.startswith("changeme")}
    assert check_environment(values, APP_REQUIREMENTS + TEST_REQUIREMENTS) == []
    assert credentials_distinct(values) == []
    assert len({values[n] for n in names}) == len(names), "every secret is distinct"
    assert values["DB_PORT"] == "5433", "non-secret settings are copied unchanged"


def test_example_placeholders_are_rejected_by_preflight():
    assert check_environment(parse(ROOT / ".env.example"), APP_REQUIREMENTS) != []


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_generated_env_is_owner_only(tmp_path):
    target = tmp_path / ".env"
    dev.generate_env(ROOT / ".env.example", target)
    assert target.stat().st_mode & 0o777 == 0o600


def test_generate_env_never_overwrites(tmp_path):
    target = tmp_path / ".env"
    target.write_text("KEEP=1\n")
    with pytest.raises(FileExistsError):
        dev.generate_env(ROOT / ".env.example", target)
    assert target.read_text() == "KEEP=1\n"


def test_record_appends_one_json_line(tmp_path):
    ledger = tmp_path / "results_ledger.jsonl"
    results = [dev.Result(0, "3 passed", 1.2), dev.Result(1, "1 failed", 0.5)]
    dev.record("test demo", results, {"a": 1}, ledger)
    dev.record("lint", [dev.Result(0, "", 0.1)], {}, ledger)
    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [e["command"] for e in entries] == ["test demo", "lint"]
    assert entries[0]["outcome"] == "FAIL" and entries[0]["seconds"] == 1.7
    assert entries[1]["outcome"] == "PASS"
    assert set(entries[0]) >= {"at", "git_commit", "peak_child_rss_mb", "details"}
