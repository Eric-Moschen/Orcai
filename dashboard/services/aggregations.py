"""
Agregações e séries para o painel (sem lógica de regras de negócio de insights).
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import Category, RecurringBill, Transaction, TransactionType
from finance.services.recurring import get_or_create_occurrence


def previous_period_bounds(date_from: date, date_to: date) -> tuple[date, date]:
    """Período anterior com a mesma duração (imediatamente antes de date_from)."""
    days = (date_to - date_from).days + 1
    prev_end = date_from - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start, prev_end


def period_totals(user, date_from: date, date_to: date) -> dict[str, Decimal]:
    qs = Transaction.objects.filter(
        user=user,
        occurred_on__gte=date_from,
        occurred_on__lte=date_to,
    )
    income = qs.filter(transaction_type=TransactionType.INCOME).aggregate(
        s=Coalesce(Sum("amount"), Decimal("0"))
    )["s"]
    expense = qs.filter(transaction_type=TransactionType.EXPENSE).aggregate(
        s=Coalesce(Sum("amount"), Decimal("0"))
    )["s"]
    if income is None:
        income = Decimal("0")
    if expense is None:
        expense = Decimal("0")
    return {
        "income": income,
        "expense": expense,
        "balance": income - expense,
    }


def pct_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        if current == 0:
            return None
        return 100.0
    return float((current - previous) / previous * 100)


def expense_by_category_rows(user, date_from: date, date_to: date) -> list[dict[str, Any]]:
    qs = (
        Transaction.objects.filter(
            user=user,
            occurred_on__gte=date_from,
            occurred_on__lte=date_to,
            transaction_type=TransactionType.EXPENSE,
        )
        .values("category_id", "category__name", "category__color")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0")))
        .order_by("-total")
    )
    rows = list(qs)
    total_exp = sum((r["total"] or Decimal("0")) for r in rows)
    out = []
    for r in rows:
        cid = r["category_id"]
        name = r["category__name"] if cid else "Sem categoria"
        color = r["category__color"] if cid and r["category__color"] else "#64748b"
        amt = r["total"] or Decimal("0")
        pct = (amt / total_exp) if total_exp > 0 else Decimal("0")
        out.append(
            {
                "category_id": cid,
                "name": name,
                "color": color,
                "amount": amt,
                "percent": float(pct * 100) if total_exp > 0 else 0.0,
            }
        )
    return out


def daily_evolution_series(user, date_from: date, date_to: date) -> list[dict[str, Any]]:
    """Por dia: receitas, despesas, líquido e saldo acumulado (fluxo, a partir de zero no início do período)."""
    qs = Transaction.objects.filter(
        user=user,
        occurred_on__gte=date_from,
        occurred_on__lte=date_to,
    ).values("occurred_on", "transaction_type", "amount")
    per_day: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0")}
    )
    for row in qs:
        d = row["occurred_on"]
        amt = row["amount"] or Decimal("0")
        if row["transaction_type"] == TransactionType.INCOME:
            per_day[d]["income"] += amt
        else:
            per_day[d]["expense"] += amt
    out = []
    cumulative = Decimal("0")
    d = date_from
    while d <= date_to:
        inc = per_day[d]["income"]
        exp = per_day[d]["expense"]
        net = inc - exp
        cumulative += net
        out.append(
            {
                "date": d.isoformat(),
                "label": d.strftime("%d/%m"),
                "income": inc,
                "expense": exp,
                "net": net,
                "cumulative": cumulative,
            }
        )
        d += timedelta(days=1)
    return out


def next_due_on_or_after(bill: RecurringBill, start: date) -> date:
    """Próxima data de vencimento (dia do mês) em ou após `start`."""
    y, m = start.year, start.month
    for _ in range(0, 24):
        last = monthrange(y, m)[1]
        day = min(bill.due_day, last)
        cand = date(y, m, day)
        if cand >= start:
            return cand
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return start


@dataclass
class UpcomingBill:
    bill: RecurringBill
    due_date: date
    occurrence_is_paid: bool
    days_until: int


def upcoming_recurring_within(
    user,
    *,
    horizon_days: int = 7,
    today: date | None = None,
) -> list[UpcomingBill]:
    today = today or timezone.localdate()
    end = today + timedelta(days=horizon_days)
    bills = RecurringBill.objects.filter(user=user, is_active=True).select_related("category")
    result: list[UpcomingBill] = []
    for b in bills:
        nd = next_due_on_or_after(b, today)
        if today <= nd <= end:
            occ = get_or_create_occurrence(b, nd.year, nd.month)
            result.append(
                UpcomingBill(
                    bill=b,
                    due_date=nd,
                    occurrence_is_paid=occ.is_paid,
                    days_until=(nd - today).days,
                )
            )
    result.sort(key=lambda x: (x.due_date, x.bill.due_day))
    return result


def recent_transactions(user, limit: int = 8) -> list[Transaction]:
    return list(
        Transaction.objects.filter(user=user)
        .select_related("category")
        .order_by("-occurred_on", "-pk")[:limit]
    )


def average_monthly_expense_history(
    user, months: int = 3, anchor: date | None = None
) -> Decimal:
    """Média de despesas dos últimos `months` meses calendário completos anteriores ao mês de `anchor`."""
    anchor = anchor or timezone.localdate()
    y, m = anchor.year, anchor.month
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    totals: list[Decimal] = []
    for _ in range(months):
        last = monthrange(y, m)[1]
        df = date(y, m, 1)
        dt = date(y, m, last)
        totals.append(period_totals(user, df, dt)["expense"])
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    if not totals:
        return Decimal("0")
    return sum(totals, Decimal("0")) / Decimal(len(totals))


def build_dashboard_data(user, date_from: date, date_to: date) -> dict[str, Any]:
    """Pacote principal de números para view e insights."""
    prev_from, prev_to = previous_period_bounds(date_from, date_to)
    cur = period_totals(user, date_from, date_to)
    prev = period_totals(user, prev_from, prev_to)
    cat_rows = expense_by_category_rows(user, date_from, date_to)
    daily = daily_evolution_series(user, date_from, date_to)
    avg_hist = average_monthly_expense_history(user, months=3, anchor=date_from)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "prev_from": prev_from,
        "prev_to": prev_to,
        "totals": cur,
        "prev_totals": prev,
        "pct_income": pct_change(cur["income"], prev["income"]),
        "pct_expense": pct_change(cur["expense"], prev["expense"]),
        "pct_balance": pct_change(cur["balance"], prev["balance"]),
        "expense_by_category": cat_rows,
        "daily": daily,
        "avg_monthly_expense_history": avg_hist,
    }
