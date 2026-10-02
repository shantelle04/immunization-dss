"""Prototype walkthrough (proposal 3.2.2): retrieval latency, query accuracy against simulator truth, the
defaulter oracle, and import-cleaning scores against the planted-defect answer key.

Evaluation only: this package is not an installed app and has no URL, so truth/ never reaches the API or UI.
Everything it does inside the database is rolled back.

Usage (from backend/): python -m evaluation.walkthrough <run_dir> [--out <markdown file>]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import django
import pandas as pd

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.accounts.models import Role, User  # noqa: E402
from apps.analytics_api.services import Reference, validate_immunizations, validate_stock  # noqa: E402
from apps.common import today  # noqa: E402
from apps.facilities.models import Facility  # noqa: E402
from apps.inventory import forecasting  # noqa: E402
from apps.inventory.models import ForecastRun  # noqa: E402
from apps.inventory.services import balance  # noqa: E402
from apps.passport.models import Antigen, Child  # noqa: E402

from . import defaulter_oracle  # noqa: E402

SEED = 20260929
CHILD_SAMPLE = 200
REPEATS = 5


def _csv(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(round(0.95 * len(ordered))) - 1)]


def latency(clients: dict[str, APIClient], children: list[Child]) -> list[dict]:
    rows = []
    endpoints = {
        "stock balance": lambda c, _: c.get("/api/v1/stock/balance"),
        "defaulter list": lambda c, _: c.get("/api/v1/defaulters"),
        "child history": lambda c, ch: c.get(f"/api/v1/children/{ch.pk}/immunizations"),
        "child search": lambda c, ch: c.get("/api/v1/children/search", {"system_id": ch.system_id}),
        "child FHIR export": lambda c, ch: c.get(f"/api/v1/children/{ch.pk}/fhir"),
        "overview": lambda c, _: c.get("/api/v1/dashboard"),
        "forecasts": lambda c, _: c.get("/api/v1/forecasts"),
        "alerts": lambda c, _: c.get("/api/v1/alerts"),
    }
    by_facility = defaultdict(list)
    for child in children:
        by_facility[child.registration_facility.code].append(child)
    for name, call in endpoints.items():
        timings = []
        for code, client in clients.items():
            sample = by_facility.get(code) or [None]
            for i in range(REPEATS):
                child = sample[i % len(sample)]
                if child is None and name.startswith("child"):
                    continue
                start = time.perf_counter()
                response = call(client, child)
                timings.append((time.perf_counter() - start) * 1000)
                assert response.status_code == 200, (name, response.status_code)
        rows.append(
            {
                "endpoint": name,
                "calls": len(timings),
                "median_ms": round(statistics.median(timings), 1),
                "p95_ms": round(_p95(timings), 1),
                "max_ms": round(max(timings), 1),
            }
        )
    return rows


def accuracy(run_dir: Path, clients: dict[str, APIClient], children: list[Child]) -> list[dict]:
    rows = []
    # 1. Stock balance per facility and antigen equals the simulator's true closing stock of the last week.
    weekly = _csv(run_dir / "truth" / "weekly_stock.csv")
    last = {}
    for r in weekly:
        key = (r["facility_code"], r["antigen_code"])
        if key not in last or r["week_start"] > last[key]["week_start"]:
            last[key] = r
    facilities = {f.code: f.pk for f in Facility.objects.all()}
    antigens = {a.code: a.pk for a in Antigen.objects.all()}
    matches = sum(
        balance(facilities[f], antigens[a]) == int(r["closing_doses"]) for (f, a), r in last.items()
    )
    rows.append({"query": "stock balance vs true closing stock", "checked": len(last), "exact": matches})

    # 2. A child's history from the API equals the doses the simulator recorded for that child.
    events = defaultdict(set)
    for r in _csv(run_dir / "app" / "immunization_events.csv"):
        events[r["child_id"]].add((r["dose_code"], r["given_on"]))
    exact = 0
    for child in children:
        client = clients[child.registration_facility.code]
        data = client.get(f"/api/v1/children/{child.pk}/immunizations").data
        api = {(h["dose_code"], str(h["given_on"])) for h in data["history"]}
        exact += api == events[child.source_ref]
    rows.append({"query": "child history vs recorded doses", "checked": len(children), "exact": exact})

    # 3. Registry size equals the number of children the simulator registered.
    truth_registered = sum(r["registered"] == "True" for r in _csv(run_dir / "truth" / "children_truth.csv"))
    rows.append(
        {
            "query": "registered children vs truth",
            "checked": 1,
            "exact": int(Child.objects.count() == truth_registered),
        }
    )
    rows += defaulter_checks(run_dir, clients)
    rows += forecast_checks(run_dir)
    for row in rows:
        row["accuracy_pct"] = round(100 * row["exact"] / row["checked"], 2)
    return rows


def defaulter_checks(run_dir: Path, clients: dict[str, APIClient]) -> list[dict]:
    """The API defaulter list against the independent oracle, for every facility (doc 05 section 3)."""
    frames = defaulter_oracle.load(run_dir)
    children = status_ok = doses_ok = facilities_ranked = 0
    under_two = frames[0][
        (pd.Timestamp(today()) - frames[0]["date_of_birth"]).dt.days.between(
            0, defaulter_oracle.LIST_UNDER_DAYS - 1
        )
    ]
    for code, client in clients.items():
        oracle = defaulter_oracle.expected(*frames, code, today())
        api = [
            (d["system_id"], sorted(d["overdue"])) for d in client.get("/api/v1/defaulters").data["results"]
        ]
        want, got = dict(oracle), dict(api)
        for system_id in under_two.loc[under_two["registration_facility_code"] == code, "system_id"]:
            children += 1
            status_ok += (system_id in want) == (system_id in got)
            doses_ok += want.get(system_id) == got.get(system_id)
        facilities_ranked += [s for s, _ in oracle] == [s for s, _ in api]
    return [
        {"query": "defaulter status vs oracle (children under 2)", "checked": children, "exact": status_ok},
        {"query": "overdue dose list vs oracle (children under 2)", "checked": children, "exact": doses_ok},
        {
            "query": "defaulter rank order vs oracle (facilities)",
            "checked": len(clients),
            "exact": facilities_ranked,
        },
    ]


def forecast_checks(run_dir: Path) -> list[dict]:
    """7. The series the application builds from its database equals the training series, byte for byte."""
    reference = run_dir.parents[2] / "analytics" / "configs" / "evidence_hashes.json"
    if not reference.exists():
        return []
    wanted = json.loads(reference.read_text())
    if wanted["run_id"] != run_dir.name:
        return []
    series = forecasting.weekly_series(forecasting.ledger_frame(), today())
    same = forecasting.series_sha256(series) == wanted["weekly_issues_sha256"]
    rows = [
        {
            "query": "weekly series from the database vs training series (SHA-256)",
            "checked": 1,
            "exact": int(same),
        }
    ]
    run = ForecastRun.objects.order_by("-run_at").first()
    if run:
        rows.append(
            {
                "query": "latest forecast run used that series",
                "checked": 1,
                "exact": int(run.data_sha256 == wanted["weekly_issues_sha256"]),
            }
        )
    return rows


def ingestion(run_dir: Path) -> list[dict]:
    """Recall per planted defect type and false rejections of clean rows, file-level rules only."""
    key = defaultdict(dict)
    for r in _csv(run_dir / "imports" / "import_dirty_truth.csv"):
        key[r["file"]][int(r["row_index"])] = r["defect"]
    ref = Reference.from_database(check_existing=False)
    rows = []
    for file, name, validate in [
        ("immunizations", "import_immunizations_dirty.csv", validate_immunizations),
        ("stock", "import_stock_dirty.csv", validate_stock),
    ]:
        data = _csv(run_dir / "imports" / name)
        found = validate(data, ref, today())
        planted = key[file]
        for defect, n in sorted(Counter(planted.values()).items()):
            idx = [i for i, d in planted.items() if d == defect]
            rows.append(
                {
                    "file": file,
                    "defect": defect,
                    "planted": n,
                    "caught_any": sum(i in found for i in idx),
                    "caught_exact": sum(found.get(i, ("",))[0] == defect for i in idx),
                }
            )
        clean = [i for i in range(len(data)) if i not in planted]
        rows.append(
            {
                "file": file,
                "defect": "(clean rows wrongly rejected)",
                "planted": len(clean),
                "caught_any": sum(i in found for i in clean),
                "caught_exact": None,
            }
        )
    return rows


def _md(rows: list[dict]) -> str:
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.run_dir / "manifest.json").read_text())
    rng = random.Random(SEED)
    with transaction.atomic():
        clients = {}
        for facility in Facility.objects.order_by("code"):
            user = User(username=f"eval-{facility.code}", role=Role.HEALTHCARE_WORKER, facility=facility)
            user.set_unusable_password()
            user.save()
            client = APIClient(HTTP_HOST="localhost")
            client.force_authenticate(user)
            clients[facility.code] = client
        pool = sorted(Child.objects.values_list("pk", flat=True))
        chosen = rng.sample(pool, CHILD_SAMPLE)
        children = list(Child.objects.select_related("registration_facility").filter(pk__in=chosen))
        result = {
            "run_id": manifest["run_id"],
            "clinical_today": str(today()),
            "latency": latency(clients, children),
            "accuracy": accuracy(args.run_dir, clients, children),
            "ingestion": ingestion(args.run_dir),
        }
        transaction.set_rollback(True)
    print(json.dumps(result, indent=2, default=str))
    if args.out:
        args.out.write_text(
            f"# Prototype walkthrough: {result['run_id']}\n\n"
            f"Generated by `python -m evaluation.walkthrough` (seed {SEED}, {CHILD_SAMPLE} sampled children, "
            f"{REPEATS} calls per endpoint per facility, in-process Django test client without network time; "
            f"clinical today {result['clinical_today']}; DEBUG={settings.DEBUG}).\n\n"
            f"## Retrieval latency\n\n{_md(result['latency'])}\n\n"
            f"## Query accuracy against simulator truth\n\n{_md(result['accuracy'])}\n\n"
            f"## Import cleaning against the planted-defect answer key (file-level rules)\n\n"
            f"{_md(result['ingestion'])}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
