"""Discrete-event simulation of immunization visits and vaccine stock across facilities.

Time moves session by session. Every Monday each facility and antigen runs stock housekeeping
(deliveries, open-vial expiry, losses, reordering). Visits before `start_date` are the children's
earlier history and are not limited by stock; from `start_date` onwards every dose needs stock.
"""

from __future__ import annotations

import bisect
import datetime as dt
import heapq
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .behaviour import Params, Series, draw_plan, offer, planned_visit, record_given
from .config import SimConfig
from .population import Children, facilities_frame, generate_children
from .stock import StockPoint

CONTACT_VISIT, REVISIT = 0, 1
HISTORIC_LOT = "HISTORIC"


@dataclass
class SimResult:
    tables: dict[str, pd.DataFrame]
    truth: dict[str, pd.DataFrame]


def _iso(o: int) -> str:
    return dt.date.fromordinal(int(o)).isoformat()


class Sessions:
    def __init__(self, cfg: SimConfig, facilities: pd.DataFrame, rng: np.random.Generator):
        sess = cfg.section("sessions")
        start, end = cfg.sim_start.toordinal(), cfg.end_date.toordinal()
        rows = []
        for fi, f in enumerate(cfg.facilities):
            place = facilities.loc[fi, "name"].split(" ")[0]
            points = [f"{place} {s} outreach point" for s in ("North", "Market", "Church", "School")]
            fixed_days = set(sess["fixed_days"][f.level])
            for d in range(start, end):
                if dt.date.fromordinal(d).weekday() in fixed_days:
                    rows.append((d, fi, "fixed", f"{facilities.loc[fi, 'name']}"))
            month = dt.date.fromordinal(start).replace(day=1)
            while month.toordinal() < end:
                nxt = (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
                weekdays = [
                    d
                    for d in range(month.toordinal(), nxt.toordinal())
                    if dt.date.fromordinal(d).weekday() < 5 and start <= d < end
                ]
                k = min(sess["outreach_per_month"][f.level], len(weekdays))
                for d in sorted(rng.choice(weekdays, size=k, replace=False)) if k else []:
                    rows.append((int(d), fi, "outreach", str(rng.choice(points))))
                month = nxt
        rows.sort()
        self.frame = pd.DataFrame(rows, columns=["date", "facility_idx", "kind", "location_name"])
        self.frame.insert(0, "session_id", [f"S{i:07d}" for i in range(len(self.frame))])
        self.window = int(sess["outreach_window_days"])
        self.fixed: dict[int, tuple[list[int], list[int]]] = {}
        self.outreach: dict[int, tuple[list[int], list[int]]] = {}
        for (fi, kind), grp in self.frame.groupby(["facility_idx", "kind"]):
            target = self.fixed if kind == "fixed" else self.outreach
            target[int(fi)] = (grp.date.tolist(), grp.index.tolist())

    def snap(self, facility: int, date: int, far: bool) -> tuple[int, int] | None:
        """(date, session row) of the session a child attends on or after `date`."""
        if far and facility in self.outreach:
            dates, idx = self.outreach[facility]
            k = bisect.bisect_left(dates, date)
            if k < len(dates) and dates[k] - date <= self.window:
                return dates[k], idx[k]
        dates, idx = self.fixed[facility]
        k = bisect.bisect_left(dates, date)
        return (dates[k], idx[k]) if k < len(dates) else None


class Engine:
    def __init__(self, cfg: SimConfig, params: Params):
        self.cfg = cfg
        self.params = params
        seeds = np.random.SeedSequence(cfg.seed).spawn(6)
        self.rng_pop, self.rng_plan, self.rng_sess, self.rng_visit, self.rng_stock, self.rng_lot = (
            np.random.default_rng(s) for s in seeds
        )
        self.series = Series.from_config(cfg)
        self.stock_cfg = cfg.section("stock")
        self.start = cfg.start_date.toordinal()
        self.sim_start = cfg.sim_start.toordinal()
        self.end = cfg.end_date.toordinal()
        self.first_stock_week = cfg.warmup_weeks
        self.n_weeks = cfg.warmup_weeks + cfg.weeks
        batching = cfg.section("sessions").get("batching") or {}
        self.batch_antigens_at: dict[int, set[str]] = {
            fi: {a for a, levels in (batching.get("levels_by_antigen") or {}).items() if f.level in levels}
            for fi, f in enumerate(cfg.facilities)
        }
        self.batch_weekday = batching.get("weekday")
        self.batch_return = float(batching.get("return_probability", 0.0))
        self.discard_probability = float(self.stock_cfg.get("open_vial_discard_probability", 0.0))

    # ------------------------------------------------------------------ setup
    def _expected_weekly_use(self, fi: int, antigen: str) -> float:
        doses_per_child = len(self.series.doses[antigen])
        return self.cfg.facilities[fi].births_per_week * doses_per_child * 1.1

    def _init_stock(self) -> None:
        self.stock: dict[tuple[int, str], StockPoint] = {}
        self.order_offset = self.rng_stock.integers(
            0, self.stock_cfg["cycle_weeks"], size=len(self.cfg.facilities)
        )
        for fi in range(len(self.cfg.facilities)):
            for code, a in self.cfg.antigens.items():
                sp = StockPoint(code, a.doses_per_vial, a.open_vial_policy)
                opening = sp.round_to_vials(
                    self.stock_cfg["max_stock_weeks"] * self._expected_weekly_use(fi, code)
                )
                lot, expiry = self._new_lot(code, self.start)
                sp.receive(opening, lot, expiry)
                self.stock[(fi, code)] = sp
                self._tx(self.start, fi, code, lot, "opening_balance", opening, "")

    def _new_lot(self, antigen: str, date: int) -> tuple[str, int]:
        self.lot_seq += 1
        year = dt.date.fromordinal(date).year
        return f"{antigen}-{year}-{self.lot_seq:05d}", date + int(self.rng_lot.integers(180, 720))

    def _tx(self, date: int, fi: int, antigen: str, lot: str, kind: str, qty: int, session_id: str) -> None:
        self.transactions.append(
            (_iso(date), self.cfg.facilities[fi].code, antigen, lot, kind, int(qty), session_id)
        )

    # ------------------------------------------------------------ stock week
    def _disruption_fill(self, antigen: str, week: int) -> float:
        for d in self.stock_cfg.get("disruptions") or []:
            rel = week - self.first_stock_week
            if d["antigen"] == antigen and d["start_week"] <= rel < d["start_week"] + d["weeks"]:
                return float(d["fill_rate"])
        return 1.0

    def _deliver_quantity(self, sp: StockPoint, antigen: str, qty: int, arrival_week: int) -> int:
        s = self.stock_cfg
        u = self.rng_stock.random()
        if u < s["delivery_skip_probability"]:
            return 0
        if u < s["delivery_skip_probability"] + s["delivery_partial_probability"]:
            qty = qty * s["partial_fill_rate"]
        doses = qty * self._disruption_fill(antigen, arrival_week)
        return int(doses // sp.doses_per_vial) * sp.doses_per_vial

    def _housekeep(self, week: int) -> None:
        monday = self.sim_start + 7 * week
        s = self.stock_cfg
        rel = week - self.first_stock_week
        for (fi, antigen), sp in self.stock.items():
            key = (fi, antigen, week)
            prev = self.weekly.get((fi, antigen, week - 1))
            if prev is not None:
                prev["closing_doses"] = sp.total()
                sp.usage.append(prev["administered_doses"] + prev["wastage_doses"])
            row = self.weekly[key] = {
                "opening_doses": sp.total(),
                "receipts_doses": 0,
                "requested_doses": 0,
                "administered_doses": 0,
                "unmet_doses": 0,
                "vials_opened": 0,
                "wastage_doses": 0,
                "loss_doses": 0,
                "in_disruption": self._disruption_fill(antigen, week) < 1.0,
            }
            expired = sp.expire_open_vial(monday)
            if expired:
                row["wastage_doses"] += expired
                self._tx(monday, fi, antigen, sp.open_lot, "wastage", -expired, "")

            arrived = [p for p in sp.pending if p[0] <= week]
            sp.pending = [p for p in sp.pending if p[0] > week]
            for _, qty in arrived:
                lot, expiry = self._new_lot(antigen, monday)
                sp.receive(qty, lot, expiry)
                row["receipts_doses"] += qty
                self._tx(monday, fi, antigen, lot, "receipt", qty, "")

            if rel % 4 == 0 and sp.sealed:
                vials = int(self.rng_stock.binomial(sp.sealed // sp.doses_per_vial, s["monthly_loss_rate"]))
                for lot, qty in sp.lose_vials(vials):
                    row["loss_doses"] += qty
                    self._tx(monday, fi, antigen, lot, "loss", -qty, "")

            avg = sp.average_weekly_use() or self._expected_weekly_use(fi, antigen)
            pipeline = sp.total() + sum(q for _, q in sp.pending)
            target = s["max_stock_weeks"] * avg
            if (rel + self.order_offset[fi]) % s["cycle_weeks"] == 0:
                qty = sp.round_to_vials(target - pipeline)
                if qty:
                    arrival = week + int(self.rng_stock.choice(s["lead_time_weeks"]))
                    delivered = self._deliver_quantity(sp, antigen, qty, arrival)
                    if delivered:
                        sp.pending.append((arrival, delivered))
            elif sp.total() < s["min_stock_weeks"] * avg and not sp.pending:
                if self.rng_stock.random() < s["emergency_fill_probability"]:
                    delivered = self._deliver_quantity(
                        sp, antigen, sp.round_to_vials(target - pipeline), week + 1
                    )
                    if delivered:
                        sp.pending.append((week + 1, delivered))

    # ------------------------------------------------------------------ visits
    def _facility_for(self, i: int, contact: int) -> int:
        ch = self.children
        if ch.moved_to[i] >= 0 and contact >= ch.move_contact[i]:
            return int(ch.moved_to[i])
        return int(ch.facility_idx[i])

    def _push(self, i: int, date: int, facility: int, kind: int, contact: int) -> None:
        if date >= self.end:
            return
        snapped = self.sessions.snap(facility, date, bool(self.children.far[i]))
        if snapped is None or snapped[0] >= self.end:
            return
        self.seq += 1
        heapq.heappush(self.heap, (snapped[0], snapped[1], self.seq, i, kind, contact))

    def _process_session(self, date: int, session_row: int, visits: list[tuple[int, int, int]]) -> None:
        sess = self.sessions.frame.loc[session_row]
        fi, session_id = int(sess.facility_idx), str(sess.session_id)
        requests: dict[str, list[tuple[int, str]]] = defaultdict(list)
        # A return visit and a scheduled contact can land on the same session; the child is seen once.
        for i in dict.fromkeys(i for i, _, _ in visits):
            if i not in self.state:
                self.state[i] = (dict(self.series.first_number), {})
                self.registration[i] = (date, fi)
            next_number, last_date = self.state[i]
            for dose in offer(
                self.cfg,
                self.series,
                self.params,
                self.rng_visit,
                date,
                int(self.children.dob[i]),
                next_number,
                last_date,
            ):
                requests[dose.split("-")[0]].append((i, dose))

        weekday = dt.date.fromordinal(date).weekday()
        if sess.kind == "fixed" and self.batch_antigens_at[fi] and weekday != self.batch_weekday:
            deferred = {i for a in self.batch_antigens_at[fi] for i, _ in requests.pop(a, [])}
            batch_day = date + (self.batch_weekday - weekday) % 7
            for i in sorted(deferred):
                if self.rng_visit.random() < self.batch_return:
                    self._push(i, batch_day, fi, REVISIT, -1)

        stock_on = date >= self.start
        week = (date - self.sim_start) // 7
        for antigen, reqs in requests.items():
            order = self.rng_visit.permutation(len(reqs))
            reqs = [reqs[k] for k in order]
            if not stock_on:
                served, lots = len(reqs), [HISTORIC_LOT] * len(reqs)
            else:
                sp = self.stock[(fi, antigen)]
                discard = (
                    sp.open_vial_policy
                    and sp.doses_per_vial > 1
                    and self.rng_visit.random() < self.discard_probability
                )
                served, vials, wasted, by_lot = sp.serve(len(reqs), date, discard)
                row = self.weekly[(fi, antigen, week)]
                row["requested_doses"] += len(reqs)
                row["administered_doses"] += served
                row["unmet_doses"] += len(reqs) - served
                row["vials_opened"] += vials
                row["wastage_doses"] += wasted
                lots = [lot for lot, q in by_lot.items() for _ in range(q)]
                for lot, q in by_lot.items():
                    self._tx(date, fi, antigen, lot, "issue", -q, session_id)
                if wasted:
                    self._tx(date, fi, antigen, sp.open_lot, "wastage", -wasted, session_id)
            for k, (i, dose) in enumerate(reqs):
                next_number, last_date = self.state[i]
                if k < served:
                    record_given(self.series, antigen, dose, date, next_number, last_date)
                    self.events.append(
                        (
                            i,
                            dose,
                            antigen,
                            int(dose.split("-")[1]),
                            _iso(date),
                            self.cfg.facilities[fi].code,
                            session_id,
                            lots[k],
                        )
                    )
                else:
                    self.stockout_turned_away.append((i, dose, _iso(date), self.cfg.facilities[fi].code))
                    if self.rng_visit.random() < self.stock_cfg["return_after_stockout"]:
                        back = date + 7 * int(self.rng_visit.integers(1, 4))
                        self._push(i, back, fi, REVISIT, -1)

        for i, kind, contact in visits:
            if kind != CONTACT_VISIT:
                continue
            nxt = contact + 1
            if nxt < len(self.cfg.contacts) and self.plan.attend[i, nxt]:
                planned = planned_visit(
                    self.cfg, int(self.children.dob[i]), nxt, int(self.plan.delay[i, nxt]), date
                )
                self._push(i, planned, self._facility_for(i, nxt), CONTACT_VISIT, nxt)

    # --------------------------------------------------------------------- run
    def run(self) -> SimResult:
        cfg = self.cfg
        self.facilities = facilities_frame(cfg, self.rng_pop)
        self.children: Children = generate_children(cfg, self.rng_pop)
        self.plan = draw_plan(cfg, self.params, self.rng_plan, self.children.dob, self.children.risk)
        self.sessions = Sessions(cfg, self.facilities, self.rng_sess)
        self.transactions: list[tuple] = []
        self.events: list[tuple] = []
        self.stockout_turned_away: list[tuple] = []
        self.weekly: dict[tuple[int, str, int], dict] = {}
        self.state: dict[int, tuple[dict, dict]] = {}
        self.registration: dict[int, tuple[int, int]] = {}
        self.lot_seq = 0
        self.heap: list[tuple] = []
        self.seq = 0
        self._init_stock()

        for i in np.flatnonzero(self.plan.entered):
            c = int(self.plan.first_contact[i])
            planned = planned_visit(cfg, int(self.children.dob[i]), c, int(self.plan.delay[i, c]), None)
            self._push(int(i), planned, self._facility_for(int(i), c), CONTACT_VISIT, c)

        next_week = self.first_stock_week
        while self.heap:
            date, row = self.heap[0][0], self.heap[0][1]
            week = (date - self.sim_start) // 7
            while date >= self.start and next_week <= week:
                self._housekeep(next_week)
                next_week += 1
            batch = []
            while self.heap and self.heap[0][0] == date and self.heap[0][1] == row:
                _, _, _, i, kind, contact = heapq.heappop(self.heap)
                batch.append((i, kind, contact))
            self._process_session(date, row, batch)
        while next_week < self.n_weeks:
            self._housekeep(next_week)
            next_week += 1
        for (fi, antigen), sp in self.stock.items():
            self.weekly[(fi, antigen, self.n_weeks - 1)]["closing_doses"] = sp.total()
        return self._collect()

    # ----------------------------------------------------------------- output
    def _collect(self) -> SimResult:
        cfg, ch = self.cfg, self.children
        child_ids = np.array([f"C{i:07d}" for i in range(len(ch))], dtype=object)
        fac_codes = np.array([f.code for f in cfg.facilities], dtype=object)
        contact_names = [c.name for c in cfg.contacts]

        facilities = self.facilities.drop(columns=["births_per_week", "residence"])
        antigens = pd.DataFrame(
            [
                {
                    "antigen_code": a.code,
                    "name": a.name,
                    "doses_per_vial": a.doses_per_vial,
                    "open_vial_policy": a.open_vial_policy,
                }
                for a in cfg.antigens.values()
            ]
        )
        contact_of = {d: c.name for c in cfg.contacts for d in c.doses}
        age_of = {d: c.age_days for c in cfg.contacts for d in c.doses}
        schedule = pd.DataFrame(
            [
                {
                    "dose_code": r.dose,
                    "antigen_code": r.antigen,
                    "dose_number": r.number,
                    "contact": contact_of[r.dose],
                    "recommended_age_days": age_of[r.dose],
                    "min_age_days": r.min_age,
                    "max_age_days": r.max_age,
                    "min_interval_days": r.min_interval,
                }
                for r in cfg.dose_rules.values()
            ]
        )

        sessions = self.sessions.frame.assign(
            date=lambda f: f.date.map(_iso),
            facility_code=lambda f: fac_codes[f.facility_idx],
        ).drop(columns=["facility_idx"])[["session_id", "facility_code", "date", "kind", "location_name"]]

        reg_rows = []
        per_facility_seq: dict[int, int] = defaultdict(int)
        for i in sorted(self.registration, key=lambda k: (self.registration[k][0], k)):
            date, fi = self.registration[i]
            per_facility_seq[fi] += 1
            reg_rows.append(
                {
                    "child_id": child_ids[i],
                    "system_id": f"IMM-{fac_codes[fi]}-{per_facility_seq[fi]:05d}",
                    "given_name": ch.given_name[i],
                    "family_name": ch.family_name[i],
                    "sex": ch.sex[i],
                    "date_of_birth": _iso(ch.dob[i]),
                    "caregiver_name": ch.caregiver_name[i],
                    "registration_facility_code": fac_codes[fi],
                    "registered_on": _iso(date),
                    "is_synthetic": True,
                }
            )
        children = pd.DataFrame(reg_rows)

        events = pd.DataFrame(
            self.events,
            columns=[
                "child_idx",
                "dose_code",
                "antigen_code",
                "dose_number",
                "given_on",
                "facility_code",
                "session_id",
                "lot_number",
            ],
        )
        events.insert(0, "child_id", child_ids[events.pop("child_idx").to_numpy()])
        events = events.sort_values(["given_on", "session_id", "child_id", "dose_code"], kind="stable")
        events.insert(0, "event_id", [f"E{i:08d}" for i in range(len(events))])
        events["is_synthetic"] = True

        tx = pd.DataFrame(
            self.transactions,
            columns=[
                "date",
                "facility_code",
                "antigen_code",
                "lot_number",
                "kind",
                "quantity_doses",
                "session_id",
            ],
        )
        tx.insert(0, "transaction_id", [f"T{i:08d}" for i in range(len(tx))])
        tx["is_synthetic"] = True
        lots = (
            tx[tx.kind.isin(["receipt", "opening_balance"])]
            .groupby(["lot_number", "antigen_code"], as_index=False)
            .date.min()
            .rename(columns={"date": "first_received"})
        )

        weekly_rows = []
        for (fi, antigen, week), r in sorted(self.weekly.items()):
            weekly_rows.append(
                {
                    "facility_code": fac_codes[fi],
                    "antigen_code": antigen,
                    "week_start": _iso(self.sim_start + 7 * week),
                    **r,
                }
            )
        weekly = pd.DataFrame(weekly_rows)
        weekly["stockout"] = (weekly.unmet_doses > 0) | (weekly.closing_doses == 0)

        dropout = self.plan.dropout_after()
        registered = np.zeros(len(ch), dtype=bool)
        registered[list(self.registration)] = True
        truth_children = pd.DataFrame(
            {
                "child_id": child_ids,
                "home_facility_code": fac_codes[ch.facility_idx],
                "date_of_birth": [_iso(d) for d in ch.dob],
                "sex": ch.sex,
                "education": ch.education,
                "wealth": ch.wealth,
                "birth_order": ch.birth_order,
                "residence": ch.residence,
                "attends_outreach": ch.far,
                "risk_log_odds": np.round(ch.risk, 4),
                "entered_care": self.plan.entered,
                "first_contact": [contact_names[c] for c in self.plan.first_contact],
                "dropout_after_contact": [contact_names[d] if d >= 0 else "" for d in dropout],
                "moved_to_facility_code": [fac_codes[m] if m >= 0 else "" for m in ch.moved_to],
                "move_from_contact": [contact_names[m] if m >= 0 else "" for m in ch.move_contact],
                "registered": registered,
            }
        )
        turned_away = pd.DataFrame(
            self.stockout_turned_away, columns=["child_idx", "dose_code", "date", "facility_code"]
        )
        turned_away.insert(0, "child_id", child_ids[turned_away.pop("child_idx").to_numpy()])

        return SimResult(
            tables={
                "facilities": facilities,
                "antigens": antigens,
                "schedule": schedule,
                "sessions": sessions,
                "children": children,
                "immunization_events": events,
                "stock_transactions": tx,
                "vaccine_lots": lots,
            },
            truth={
                "children_truth": truth_children,
                "weekly_stock": weekly,
                "stockout_turned_away": turned_away,
            },
        )
