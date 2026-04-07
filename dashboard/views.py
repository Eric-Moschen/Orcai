from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from dashboard.services.aggregations import (
    build_dashboard_data,
    recent_transactions,
    upcoming_recurring_within,
)
from dashboard.services.health_score import compute_financial_health_score, persist_health_score
from finance.services.insights import build_insights
from finance.services.period import resolve_period_from_get


def _chart_expense_by_category(rows: list[dict]) -> dict:
    if not rows:
        return {"labels": [], "datasets": []}
    return {
        "labels": [r["name"] for r in rows],
        "datasets": [
            {
                "data": [float(r["amount"]) for r in rows],
                "backgroundColor": [r["color"] for r in rows],
                "borderWidth": 0,
            }
        ],
    }


def _chart_evolution(daily: list[dict], mode: str) -> dict:
    labels = [d["label"] for d in daily]
    if mode == "flow":
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "Receitas",
                    "data": [float(d["income"]) for d in daily],
                    "borderColor": "#34d399",
                    "backgroundColor": "rgba(52,211,153,0.15)",
                    "fill": True,
                    "tension": 0.35,
                },
                {
                    "label": "Despesas",
                    "data": [float(d["expense"]) for d in daily],
                    "borderColor": "#fb7185",
                    "backgroundColor": "rgba(251,113,133,0.12)",
                    "fill": True,
                    "tension": 0.35,
                },
            ],
        }
    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Saldo acumulado (fluxo)",
                "data": [float(d["cumulative"]) for d in daily],
                "borderColor": "#4DA6FF",
                "backgroundColor": "rgba(77,166,255,0.12)",
                "fill": True,
                "tension": 0.35,
            }
        ],
    }


@login_required
def home(request):
    date_from, date_to, period_key = resolve_period_from_get(request.GET)
    evolution_mode = request.GET.get("evolution") or "cumulative"
    if evolution_mode not in ("cumulative", "flow"):
        evolution_mode = "cumulative"

    data = build_dashboard_data(request.user, date_from, date_to)
    insights = build_insights(request.user, data, today=timezone.localdate())

    top_share = None
    exp_rows = data.get("expense_by_category") or []
    if exp_rows and data["totals"]["expense"] > 0:
        top_share = float(exp_rows[0]["amount"] / data["totals"]["expense"])

    score = compute_financial_health_score(
        balance=data["totals"]["balance"],
        income=data["totals"]["income"],
        expense=data["totals"]["expense"],
        prev_expense=data["prev_totals"]["expense"],
        top_category_share=top_share,
    )
    persist_health_score(request.user, score)

    upcoming = upcoming_recurring_within(request.user, horizon_days=7)
    recent = recent_transactions(request.user, 8)

    pie_chart = _chart_expense_by_category(exp_rows)
    line_chart = _chart_evolution(data["daily"], evolution_mode)

    p = request.GET.copy()
    p.pop("page", None)
    qs_nopage = urlencode(p)

    context = {
        "page_title": "Painel",
        "filter_date_from": date_from,
        "filter_date_to": date_to,
        "period": period_key,
        "evolution_mode": evolution_mode,
        "data": data,
        "insights": insights,
        "health_score": score,
        "upcoming": upcoming,
        "recent": recent,
        "pie_chart": pie_chart,
        "line_chart": line_chart,
        "qs_nopage": qs_nopage,
    }
    return render(request, "dashboard/home.html", context)
