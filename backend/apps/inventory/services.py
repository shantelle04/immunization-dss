"""Stock ledger (FR-10, FR-11, BR-06). The balance is always the sum of transactions, never stored."""

from __future__ import annotations

from datetime import date, timedelta

from django.db import connection, transaction
from django.db.models import Sum

from apps.accounts.models import AuditAction, User
from apps.accounts.services import audit
from apps.common import today
from apps.facilities.models import Facility
from apps.passport.models import Antigen

from .models import INBOUND, OUTBOUND, StockTransaction, TxKind

USE_WINDOW_WEEKS = 12  # weeks of recent issues and wastage used for "weeks of stock left"


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
