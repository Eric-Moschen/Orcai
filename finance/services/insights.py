"""
Mensagens inteligentes a partir de agregações do dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import Transaction, TransactionType


@dataclass
class Insight:
    text: str
    tone: str = "neutral"  # positive | warning | danger | neutral


def _fmt_money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _expense_in_range(user, d0: date, d1: date) -> Decimal:
    r = Transaction.objects.filter(
        user=user,
        occurred_on__gte=d0,
        occurred_on__lte=d1,
        transaction_type=TransactionType.EXPENSE,
    ).aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"]
    return r or Decimal("0")


def build_insights(
    user,
    data: dict[str, Any],
    *,
    today: date | None = None,
) -> list[Insight]:
    today = today or timezone.localdate()
    insights: list[Insight] = []
    totals = data["totals"]
    prev = data["prev_totals"]
    pct_exp = data.get("pct_expense")
    cat_rows: list[dict] = data.get("expense_by_category") or []
    avg_hist: Decimal = data.get("avg_monthly_expense_history") or Decimal("0")
    daily = data.get("daily") or []
    date_from: date = data["date_from"]
    date_to: date = data["date_to"]

    if pct_exp is not None and prev["expense"] > 0:
        if pct_exp > 1:
            insights.append(
                Insight(
                    text=f"Você gastou {pct_exp:.1f}% a mais que no período anterior.",
                    tone="warning",
                )
            )
        elif pct_exp < -1:
            insights.append(
                Insight(
                    text=(
                        f"Seus gastos caíram {abs(pct_exp):.1f}% em relação ao período anterior. "
                        "Bom sinal."
                    ),
                    tone="positive",
                )
            )

    if cat_rows and totals["expense"] > 0:
        top = cat_rows[0]
        pct = float(top.get("percent") or 0)
        if pct >= 25:
            insights.append(
                Insight(
                    text=(
                        f'"{top["name"]}" representa cerca de {pct:.0f}% dos seus gastos no período.'
                    ),
                    tone="neutral",
                )
            )

    if avg_hist > 0 and totals["expense"] > 0:
        diff = totals["expense"] - avg_hist
        if diff > avg_hist * Decimal("0.15"):
            insights.append(
                Insight(
                    text=(
                        "Gastos acima da sua média dos últimos 3 meses completos "
                        f"(~{_fmt_money(avg_hist)} / mês). Vale revisar as maiores categorias."
                    ),
                    tone="warning",
                )
            )

    days = (date_to - date_from).days + 1
    if days > 0 and totals["expense"] > totals["income"]:
        daily_net = totals["balance"] / Decimal(days)
        if daily_net < 0:
            insights.append(
                Insight(
                    text=(
                        "No ritmo médio deste período, o resultado diário é negativo. "
                        "Considere cortar gastos variáveis ou antecipar receitas."
                    ),
                    tone="danger",
                )
            )

    for row in daily:
        if row["cumulative"] < 0:
            d = date.fromisoformat(row["date"])
            insights.append(
                Insight(
                    text=(
                        f"A partir de {d.strftime('%d/%m/%Y')}, o saldo acumulado do período "
                        "(fluxo) ficou negativo."
                    ),
                    tone="warning",
                )
            )
            break

    if cat_rows and totals["expense"] > 0:
        top = cat_rows[0]
        save = (top["amount"] * Decimal("0.05")).quantize(Decimal("0.01"))
        if save >= Decimal("5"):
            insights.append(
                Insight(
                    text=(
                        f'Você pode economizar cerca de {_fmt_money(save)} '
                        f'reduzindo ~5% em "{top["name"]}".'
                    ),
                    tone="positive",
                )
            )

    end = today
    start_7 = end - timedelta(days=6)
    prev_end = start_7 - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    e7 = _expense_in_range(user, start_7, end)
    p7 = _expense_in_range(user, prev_start, prev_end)
    if p7 > 0 and e7 > p7 * Decimal("1.25"):
        insights.append(
            Insight(
                text="Na última semana seus gastos subiram forte em relação à semana anterior.",
                tone="warning",
            )
        )

    return insights[:8]
