"""Synthetic facilities and children: births, background characteristics, names, mobility."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import SimConfig

LEVEL_LABEL = {
    "dispensary": "Dispensary",
    "health_centre": "Health Centre",
    "sub_county_hospital": "Sub-County Hospital",
}
PLACE_PREFIX = ["Ki", "Ma", "Nya", "Mu", "Ka", "Tu", "Olo", "Ga", "Chi", "Lu", "Ruk", "Wa", "Ndo", "Se"]
PLACE_SUFFIX = ["rembo", "tamu", "kiri", "sanga", "rura", "wendo", "biru", "lolo", "nyeri", "gathi", "mani"]
GIVEN_FEMALE = [
    "Achieng",
    "Wanjiru",
    "Njeri",
    "Akinyi",
    "Chebet",
    "Wambui",
    "Nafula",
    "Atieno",
    "Mumbua",
    "Jepkoech",
    "Faith",
    "Grace",
    "Mercy",
    "Joy",
    "Esther",
    "Mary",
    "Amina",
    "Halima",
    "Neema",
    "Zawadi",
]
GIVEN_MALE = [
    "Otieno",
    "Kamau",
    "Mwangi",
    "Kiprono",
    "Omondi",
    "Mutua",
    "Wafula",
    "Kipchoge",
    "Njoroge",
    "Barasa",
    "Brian",
    "Kevin",
    "Dennis",
    "Ian",
    "Samuel",
    "John",
    "Hassan",
    "Ali",
    "Baraka",
    "Imani",
]
FAMILY = [
    "Odhiambo",
    "Kariuki",
    "Mutiso",
    "Cheruiyot",
    "Wekesa",
    "Ochieng",
    "Maina",
    "Kiplagat",
    "Nduta",
    "Owino",
    "Githinji",
    "Makau",
    "Rotich",
    "Simiyu",
    "Onyango",
    "Waweru",
    "Kimani",
    "Juma",
    "Mohamed",
    "Chege",
]


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def facilities_frame(cfg: SimConfig, rng: np.random.Generator) -> pd.DataFrame:
    used: set[str] = set()
    rows = []
    for f in cfg.facilities:
        while True:
            place = str(rng.choice(PLACE_PREFIX)) + str(rng.choice(PLACE_SUFFIX))
            if place not in used:
                used.add(place)
                break
        rows.append(
            {
                "facility_code": f.code,
                "name": f"{place} {LEVEL_LABEL.get(f.level, f.level.title())}",
                "keph_level": f.level,
                "ownership": f.ownership,
                "residence": f.residence,
                "county": cfg.county,
                "sub_county": f"{place} Sub-County" if f.level == "sub_county_hospital" else "",
                "births_per_week": f.births_per_week,
                "is_synthetic": True,
            }
        )
    frame = pd.DataFrame(rows)
    hospitals = frame[frame.keph_level == "sub_county_hospital"]
    for idx in frame.index[frame.sub_county == ""]:
        frame.loc[idx, "sub_county"] = (
            hospitals.sub_county.iloc[idx % len(hospitals)] if len(hospitals) else "Central"
        )
    return frame


def group_effects(cfg: SimConfig) -> dict[str, dict[str, float]]:
    """Log-odds shift of each category relative to the national Penta3 coverage, shrunk for independence."""
    cal = cfg.section("calibration")
    base = logit(cal["targets"]["penta3"])
    shrink = cal["effect_shrink"]
    return {
        group: {cat: shrink * (logit(p) - base) for cat, p in values.items()}
        for group, values in cal["penta3_by_group"].items()
    }


@dataclass
class Children:
    facility_idx: np.ndarray
    dob: np.ndarray
    sex: np.ndarray
    education: np.ndarray
    wealth: np.ndarray
    birth_order: np.ndarray
    residence: np.ndarray
    far: np.ndarray
    risk: np.ndarray
    moved_to: np.ndarray
    move_contact: np.ndarray
    given_name: np.ndarray
    family_name: np.ndarray
    caregiver_name: np.ndarray

    def __len__(self) -> int:
        return len(self.dob)


def _categorical(rng: np.random.Generator, counts: dict[str, float], n: int) -> np.ndarray:
    cats = list(counts)
    weights = np.array([counts[c] for c in cats], dtype=float)
    return np.array(cats, dtype=object)[rng.choice(len(cats), size=n, p=weights / weights.sum())]


def draw_background(cfg: SimConfig, rng: np.random.Generator, n: int, residence: np.ndarray) -> dict:
    pop = cfg.section("population")
    effects = group_effects(cfg)
    education = _categorical(rng, pop["education"], n)
    wealth = _categorical(rng, pop["wealth"], n)
    birth_order = _categorical(rng, pop["birth_order"], n)
    risk = (
        np.vectorize(effects["education"].get)(education)
        + np.vectorize(effects["wealth"].get)(wealth)
        + np.vectorize(effects["birth_order"].get)(birth_order)
    ).astype(float)
    far_share = cfg.section("sessions")["far_share"]
    far = rng.random(n) < np.vectorize(far_share.get)(residence).astype(float)
    return {"education": education, "wealth": wealth, "birth_order": birth_order, "risk": risk, "far": far}


def generate_children(cfg: SimConfig, rng: np.random.Generator) -> Children:
    pop = cfg.section("population")
    total_weeks = cfg.warmup_weeks + cfg.weeks
    fac_idx, dob = [], []
    sim_start = cfg.sim_start.toordinal()
    for i, f in enumerate(cfg.facilities):
        t = np.arange(total_weeks)
        lam = (
            f.births_per_week
            * (1 + pop["birth_growth_per_year"]) ** (t / 52.0)
            * (1 + pop["birth_seasonal_amplitude"] * np.sin(2 * np.pi * t / 52.0))
        )
        counts = rng.poisson(lam)
        for week, c in zip(t, counts, strict=True):
            fac_idx.extend([i] * int(c))
            dob.extend((sim_start + 7 * int(week) + rng.integers(0, 7, size=int(c))).tolist())
    fac_idx_arr = np.array(fac_idx, dtype=np.int64)
    dob_arr = np.array(dob, dtype=np.int64)
    order = np.lexsort((fac_idx_arr, dob_arr))
    fac_idx_arr, dob_arr = fac_idx_arr[order], dob_arr[order]
    n = len(dob_arr)

    residence = np.array([cfg.facilities[i].residence for i in fac_idx_arr], dtype=object)
    bg = draw_background(cfg, rng, n, residence)
    sex = np.where(rng.random(n) < 0.5, "F", "M").astype(object)

    n_fac = len(cfg.facilities)
    moved = rng.random(n) < pop["mobility_share"]
    shift = rng.integers(1, n_fac, size=n)
    moved_to = np.where(moved, (fac_idx_arr + shift) % n_fac, -1)
    move_contact = np.where(moved, rng.integers(2, len(cfg.contacts), size=n), -1)

    given = np.where(
        sex == "F",
        np.array(GIVEN_FEMALE, dtype=object)[rng.integers(0, len(GIVEN_FEMALE), n)],
        np.array(GIVEN_MALE, dtype=object)[rng.integers(0, len(GIVEN_MALE), n)],
    )
    family = np.array(FAMILY, dtype=object)[rng.integers(0, len(FAMILY), n)]
    caregiver = np.array(GIVEN_FEMALE, dtype=object)[rng.integers(0, len(GIVEN_FEMALE), n)] + " " + family

    return Children(
        facility_idx=fac_idx_arr,
        dob=dob_arr,
        sex=sex,
        education=bg["education"],
        wealth=bg["wealth"],
        birth_order=bg["birth_order"],
        residence=residence,
        far=bg["far"],
        risk=bg["risk"],
        moved_to=moved_to,
        move_contact=move_contact,
        given_name=given,
        family_name=family,
        caregiver_name=caregiver,
    )


def ordinal_to_date(o: int) -> dt.date:
    return dt.date.fromordinal(int(o))
