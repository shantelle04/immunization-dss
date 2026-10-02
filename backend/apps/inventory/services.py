"""Stock ledger (FR-10, FR-11, BR-06). The balance is always the sum of transactions, never stored."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Sum
from django.db.models.functions import TruncWeek

from apps.accounts.models import AuditAction, User
from apps.accounts.services import audit
from apps.common import today
from apps.facilities.models import Facility
from apps.passport.models import Antigen

from .models import INBOUND, OUTBOUND, Forecast, ForecastRun, StockTransaction, TxKind

USE_WINDOW_WEEKS = 12  # weeks of recent issues and wastage used for "weeks of stock left"
HISTORY_WEEKS = 26  # weeks of past issues shown beside the forecast
DEFAULT_SAFETY_BUFFER = Decimal("0.25")  # D-33


class StockRefused(Exception):
    pass


def balance(facility_id: int, antigen_id: int) -> int:
    return (
        StockTransaction.objects.filter(facility_id=facility_id, antigen_id=antigen_id).aggregate(
            b=Sum("quantity_doses")
        )["b"]
        or 0
    )


def balances(facility_id: int, on: date) -> list[dict]:
    """Current balance and weeks of stock left per antigen, from the ledger view (FR-11)."""
    since = on - timedelta(weeks=USE_WINDOW_WEEKS)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT antigen_id, balance FROM inventory_stock_balance WHERE facility_id = %s", [facility_id]
        )
        current = dict(cursor.fetchall())
    use = dict(
        StockTransaction.objects.filter(
            facility_id=facility_id, kind__in=(TxKind.ISSUE, TxKind.WASTAGE), occurred_on__gt=since
        )
        .values_list("antigen_id")
        .annotate(total=Sum("quantity_doses"))
    )
    rows = []
    for antigen in Antigen.objects.order_by("code"):
        weekly_use = -use.get(antigen.id, 0) / USE_WINDOW_WEEKS
        stock = current.get(antigen.id, 0)
        rows.append(
            {
                "antigen": antigen.code,
                "antigen_name": antigen.name,
                "balance_doses": stock,
                "weekly_use_doses": round(weekly_use, 1),
                "weeks_left": round(stock / weekly_use, 1) if weekly_use > 0 else None,
            }
        )
    return rows


@transaction.atomic
def record(user: User, antigen: Antigen, kind: str, quantity: int, occurred_on: date, lot=None, session=None):
    """Quantity is entered as a positive number of doses; the ledger sign follows the kind."""
    if occurred_on > today():
        raise StockRefused("The date cannot be in the future.")
    if kind in INBOUND:
        signed = abs(quantity)
    elif kind in OUTBOUND:
        signed = -abs(quantity)
    else:
        signed = quantity
    if signed == 0:
        raise StockRefused("The quantity cannot be zero.")
    # Serialise ledger writes for this facility so two issues cannot both pass the balance check.
    _lock(user.facility_id)
    if signed < 0 and balance(user.facility_id, antigen.id) + signed < 0:
        raise StockRefused(f"Not enough {antigen.code} in stock for this transaction.")
    tx = StockTransaction.objects.create(
        facility_id=user.facility_id,
        antigen=antigen,
        lot=lot,
        kind=kind,
        quantity_doses=signed,
        occurred_on=occurred_on,
        session=session,
        recorded_by=user,
    )
    audit(user, AuditAction.CREATE, "stock_transaction", tx.pk)
    return tx


def issue_for_dose(user: User, antigen: Antigen, lot, on: date, session=None):
    return record(user, antigen, TxKind.ISSUE, 1, on, lot=lot, session=session)


def _lock(facility_id: int) -> None:
    Facility.objects.select_for_update().get(pk=facility_id)


def forecast_overview(facility_id: int, on: date) -> dict:
    """Latest forecast run for one facility: recent weekly issues, the next 4 weeks and backtest accuracy."""
    run = ForecastRun.objects.order_by("-run_at").first()
    if run is None:
        return {"run": None, "antigens": []}
    facility_code = Facility.objects.values_list("code", flat=True).get(pk=facility_id)
    this_week = on - timedelta(days=on.weekday())
    history: dict[int, list] = {}
    for antigen_id, week, total in (
        StockTransaction.objects.filter(
            facility_id=facility_id,
            kind=TxKind.ISSUE,
            occurred_on__gte=this_week - timedelta(weeks=HISTORY_WEEKS),
            occurred_on__lt=this_week,
        )
        .annotate(week=TruncWeek("occurred_on"))
        .values_list("antigen_id", "week")
        .annotate(total=Sum("quantity_doses"))
        .order_by("week")
    ):
        history.setdefault(antigen_id, []).append((week, -total))
    forecasts: dict[int, list[Forecast]] = {}
    for f in Forecast.objects.filter(run=run, facility_id=facility_id).order_by("week_start"):
        forecasts.setdefault(f.antigen_id, []).append(f)
    by_series = (run.metrics or {}).get("by_series", {})
    rows = []
    for antigen in Antigen.objects.order_by("code"):
        future = forecasts.get(antigen.id, [])
        if not future:
            continue
        issued = dict(history.get(antigen.id, []))
        weeks = [this_week - timedelta(weeks=i) for i in range(HISTORY_WEEKS, 0, -1)]
        rows.append(
            {
                "antigen": antigen.code,
                "antigen_name": antigen.name,
                "model": future[0].model,
                "accuracy": by_series.get(f"{facility_code}|{antigen.code}"),
                "history": [{"week_start": w, "issued": issued.get(w, 0)} for w in weeks],
                "forecast": [
                    {
                        "week_start": f.week_start,
                        "yhat": float(f.yhat),
                        "lo80": float(f.lo80),
                        "hi80": float(f.hi80),
                    }
                    for f in future
                ],
            }
        )
    return {
        "run": {
            "run_at": run.run_at,
            "source": run.params.get("source"),
            "as_of": run.params.get("as_of"),
            "data_sha256": run.data_sha256[:12],
        },
        "antigens": rows,
    }
