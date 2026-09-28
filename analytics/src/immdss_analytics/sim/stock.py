"""Vaccine stock at one facility for one antigen: sealed vials by lot (FIFO), one open vial, pipeline."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

OPEN_VIAL_DAYS = 28


@dataclass
class StockPoint:
    antigen: str
    doses_per_vial: int
    open_vial_policy: bool
    sealed: int = 0
    open_doses: int = 0
    open_since: int = 0
    open_lot: str = ""
    lots: deque = field(default_factory=deque)
    pending: list = field(default_factory=list)
    usage: deque = field(default_factory=lambda: deque(maxlen=12))

    def total(self) -> int:
        return self.sealed + self.open_doses

    def receive(self, doses: int, lot: str, expiry: int) -> None:
        self.sealed += doses
        self.lots.append([lot, expiry, doses])

    def _take_vial(self) -> str:
        lot = self.lots[0]
        lot[2] -= self.doses_per_vial
        if lot[2] <= 0:
            self.lots.popleft()
        self.sealed -= self.doses_per_vial
        return lot[0]

    def serve(self, requested: int, date: int, discard: bool = False) -> tuple[int, int, int, dict[str, int]]:
        """Give up to `requested` doses at a session.

        The open vial is discarded at the end of the session when the vaccine has no open-vial policy,
        or when `discard` is set (handling wastage of an open-vial-policy vaccine).
        Returns (served, vials opened, doses wasted, served by lot).
        """
        served, vials, by_lot = 0, 0, {}
        while served < requested:
            if self.open_doses == 0:
                if self.sealed < self.doses_per_vial:
                    break
                self.open_lot = self._take_vial()
                self.open_doses = self.doses_per_vial
                self.open_since = date
                vials += 1
            take = min(self.open_doses, requested - served)
            self.open_doses -= take
            served += take
            by_lot[self.open_lot] = by_lot.get(self.open_lot, 0) + take
        wasted = 0
        if (discard or not self.open_vial_policy) and self.open_doses:
            wasted, self.open_doses = self.open_doses, 0
        return served, vials, wasted, by_lot

    def expire_open_vial(self, date: int) -> int:
        if self.open_doses and date - self.open_since >= OPEN_VIAL_DAYS:
            wasted, self.open_doses = self.open_doses, 0
            return wasted
        return 0

    def lose_vials(self, vials: int) -> list[tuple[str, int]]:
        """Remove whole sealed vials (expiry, breakage, cold chain), oldest lot first."""
        removed = []
        for _ in range(min(vials, self.sealed // self.doses_per_vial)):
            removed.append((self._take_vial(), self.doses_per_vial))
        return removed

    def average_weekly_use(self) -> float | None:
        return sum(self.usage) / len(self.usage) if len(self.usage) >= 4 else None

    def round_to_vials(self, doses: float) -> int:
        return max(0, math.ceil(doses / self.doses_per_vial)) * self.doses_per_vial
