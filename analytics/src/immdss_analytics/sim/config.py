"""Load and validate the simulator configuration, failing with every violation listed at once."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Facility:
    code: str
    level: str
    ownership: str
    residence: str
    births_per_week: float


@dataclass(frozen=True)
class Antigen:
    code: str
    name: str
    doses_per_vial: int
    open_vial_policy: bool


@dataclass(frozen=True)
class DoseRule:
    dose: str
    antigen: str
    number: int
    min_age: int
    max_age: int
    min_interval: int
    target_key: str


@dataclass(frozen=True)
class Contact:
    name: str
    age_days: int
    doses: tuple[str, ...]


@dataclass(frozen=True)
class SimConfig:
    raw: dict[str, Any]
    seed: int
    start_date: dt.date
    weeks: int
    warmup_weeks: int
    as_of_date: dt.date
    county: str
    facilities: tuple[Facility, ...]
    antigens: dict[str, Antigen]
    dose_rules: dict[str, DoseRule]
    contacts: tuple[Contact, ...]

    @property
    def sim_start(self) -> dt.date:
        return self.start_date - dt.timedelta(weeks=self.warmup_weeks)

    @property
    def end_date(self) -> dt.date:
        return self.start_date + dt.timedelta(weeks=self.weeks)

    @property
    def config_hash(self) -> str:
        # Key order is kept: the order of contacts is meaningful.
        canonical = json.dumps(self.raw, default=str).encode()
        return hashlib.sha256(canonical).hexdigest()

    def section(self, name: str) -> dict[str, Any]:
        return self.raw[name]


REQUIRED_SECTIONS = (
    "seed",
    "start_date",
    "weeks",
    "warmup_weeks",
    "as_of_date",
    "county",
    "facilities",
    "sessions",
    "population",
    "calibration",
    "timeliness",
    "stock",
    "antigens",
    "contacts",
    "dose_rules",
    "dirty_import",
)


def _as_date(value: Any, key: str, errors: list[str]) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"{key}: not an ISO date, got {value!r}")
        return dt.date(2000, 1, 3)


def _probability(value: Any, key: str, errors: list[str]) -> None:
    if not isinstance(value, int | float) or not 0.0 <= float(value) <= 1.0:
        errors.append(f"{key}: must be a probability in [0, 1], got {value!r}")


def load_config(path: str | Path, seed_override: int | None = None) -> SimConfig:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ConfigError("config: top level must be a mapping")
    if seed_override is not None:
        raw["seed"] = seed_override
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> SimConfig:
    errors: list[str] = []
    missing = [k for k in REQUIRED_SECTIONS if k not in raw]
    if missing:
        raise ConfigError("config: missing sections: " + ", ".join(missing))

    start = _as_date(raw["start_date"], "start_date", errors)
    as_of = _as_date(raw["as_of_date"], "as_of_date", errors)
    if start.weekday() != 0:
        errors.append(f"start_date: must be a Monday, got {start.isoformat()}")
    weeks, warmup = raw["weeks"], raw["warmup_weeks"]
    if not isinstance(weeks, int) or weeks < 8:
        errors.append(f"weeks: must be an integer >= 8, got {weeks!r}")
    if not isinstance(warmup, int) or warmup < 0:
        errors.append(f"warmup_weeks: must be an integer >= 0, got {warmup!r}")
    if isinstance(weeks, int) and not start <= as_of <= start + dt.timedelta(weeks=weeks):
        errors.append("as_of_date: must fall inside the simulated window")

    sessions = raw["sessions"]
    facilities: list[Facility] = []
    seen: set[str] = set()
    for i, f in enumerate(raw["facilities"] or []):
        key = f"facilities[{i}]"
        try:
            fac = Facility(
                str(f["code"]),
                str(f["level"]),
                str(f["ownership"]),
                str(f["residence"]),
                float(f["births_per_week"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{key}: invalid facility ({exc})")
            continue
        if fac.code in seen:
            errors.append(f"{key}.code: duplicate {fac.code}")
        seen.add(fac.code)
        if fac.level not in sessions["fixed_days"] or fac.level not in sessions["outreach_per_month"]:
            errors.append(f"{key}.level: no session rules for level {fac.level!r}")
        if fac.residence not in sessions["far_share"]:
            errors.append(f"{key}.residence: no far_share for {fac.residence!r}")
        if fac.births_per_week <= 0:
            errors.append(f"{key}.births_per_week: must be > 0")
        facilities.append(fac)
    if len(facilities) < 2:
        errors.append("facilities: at least two are needed (cross-facility records)")

    antigens: dict[str, Antigen] = {}
    for code, a in (raw["antigens"] or {}).items():
        dpv = a.get("doses_per_vial")
        if not isinstance(dpv, int) or dpv < 1:
            errors.append(f"antigens.{code}.doses_per_vial: must be an integer >= 1, got {dpv!r}")
            continue
        antigens[code] = Antigen(code, str(a.get("name", code)), dpv, bool(a.get("open_vial_policy")))

    doses_per_antigen: dict[str, int] = {}
    for dose in raw["dose_rules"] or {}:
        antigen = dose.split("-")[0]
        doses_per_antigen[antigen] = doses_per_antigen.get(antigen, 0) + 1

    dose_rules: dict[str, DoseRule] = {}
    for dose, r in (raw["dose_rules"] or {}).items():
        antigen, _, number = dose.partition("-")
        if antigen not in antigens or not number.isdigit():
            errors.append(f"dose_rules.{dose}: must be <ANTIGEN>-<n> with a known antigen")
            continue
        min_age, max_age, interval = r.get("min_age"), r.get("max_age"), r.get("min_interval")
        if not all(isinstance(v, int) and v >= 0 for v in (min_age, max_age, interval)):
            errors.append(f"dose_rules.{dose}: min_age, max_age, min_interval must be integers >= 0")
            continue
        if max_age < min_age:
            errors.append(f"dose_rules.{dose}: max_age < min_age")
        key = antigen.lower() if doses_per_antigen[antigen] == 1 else f"{antigen.lower()}{number}"
        dose_rules[dose] = DoseRule(dose, antigen, int(number), min_age, max_age, interval, key)

    contacts: list[Contact] = []
    for name, c in (raw["contacts"] or {}).items():
        doses = tuple(c.get("doses", []))
        for d in doses:
            if d not in dose_rules:
                errors.append(f"contacts.{name}: unknown dose {d}")
        contacts.append(Contact(name, int(c["age_days"]), doses))
    ages = [c.age_days for c in contacts]
    if ages != sorted(ages) or not contacts or contacts[0].age_days != 0:
        errors.append("contacts: must start at age 0 and be in increasing age order")
    scheduled = [d for c in contacts for d in c.doses]
    if sorted(scheduled) != sorted(dose_rules):
        errors.append("contacts: every dose rule must appear in exactly one contact")

    cal = raw["calibration"]
    for key, value in cal["targets"].items():
        _probability(value, f"calibration.targets.{key}", errors)
    known_keys = {r.target_key for r in dose_rules.values()} | {"zero_dose"}
    unknown = set(cal["targets"]) - known_keys
    if unknown:
        errors.append(f"calibration.targets: unknown keys {sorted(unknown)}")
    for group, values in cal["penta3_by_group"].items():
        if set(values) != set(raw["population"][group]):
            errors.append(f"calibration.penta3_by_group.{group}: categories differ from population.{group}")
        for cat, value in values.items():
            _probability(value, f"calibration.penta3_by_group.{group}.{cat}", errors)
    _probability(cal["effect_shrink"], "calibration.effect_shrink", errors)
    _probability(cal["first_contact_at_birth"], "calibration.first_contact_at_birth", errors)

    stock = raw["stock"]
    for key in (
        "emergency_fill_probability",
        "delivery_skip_probability",
        "delivery_partial_probability",
        "partial_fill_rate",
        "monthly_loss_rate",
        "return_after_stockout",
    ):
        _probability(stock[key], f"stock.{key}", errors)
    for i, d in enumerate(stock.get("disruptions") or []):
        if d.get("antigen") not in antigens:
            errors.append(f"stock.disruptions[{i}].antigen: unknown {d.get('antigen')!r}")
        _probability(d.get("fill_rate"), f"stock.disruptions[{i}].fill_rate", errors)
    for key in ("mobility_share", "birth_seasonal_amplitude"):
        _probability(raw["population"][key], f"population.{key}", errors)
    for res, share in sessions["far_share"].items():
        _probability(share, f"sessions.far_share.{res}", errors)
    batching = sessions.get("batching")
    if batching:
        levels_by_antigen = batching.get("levels_by_antigen") or {}
        for code in levels_by_antigen:
            if code not in antigens:
                errors.append(f"sessions.batching.levels_by_antigen: unknown antigen {code!r}")
        for level in sorted({lv for levels in levels_by_antigen.values() for lv in levels}):
            if batching.get("weekday") not in sessions["fixed_days"].get(level, []):
                errors.append(f"sessions.batching.weekday: not a static day at level {level!r}")
        _probability(batching.get("return_probability"), "sessions.batching.return_probability", errors)
    _probability(
        stock.get("open_vial_discard_probability", 0.0), "stock.open_vial_discard_probability", errors
    )
    timeliness_contacts = set(raw["timeliness"]["median_delay_days"])
    if timeliness_contacts != {c.name for c in contacts}:
        errors.append("timeliness.median_delay_days: must list every contact")

    if errors:
        raise ConfigError("invalid simulator config:\n  " + "\n  ".join(errors))

    return SimConfig(
        raw=raw,
        seed=int(raw["seed"]),
        start_date=start,
        weeks=weeks,
        warmup_weeks=warmup,
        as_of_date=as_of,
        county=str(raw["county"]),
        facilities=tuple(facilities),
        antigens=antigens,
        dose_rules=dose_rules,
        contacts=tuple(contacts),
    )
