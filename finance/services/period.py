from datetime import date, timedelta

from django.utils import timezone

from .dates import first_day_of_month, last_day_of_month


def resolve_period_from_get(get) -> tuple[date, date, str]:
    """
    Retorna (date_from, date_to, period_key) a partir dos query params.
    period: this_month | last_month | custom
    """
    period = get.get("period") or "this_month"
    today = timezone.localdate()
    if period == "last_month":
        first_this = first_day_of_month(today)
        last_prev = first_this - timedelta(days=1)
        return first_day_of_month(last_prev), last_prev, period
    if period == "custom":
        df = get.get("date_from")
        dt = get.get("date_to")
        try:
            parts_f = [int(x) for x in df.split("-")] if df else []
            parts_t = [int(x) for x in dt.split("-")] if dt else []
            if len(parts_f) == 3 and len(parts_t) == 3:
                d_from = date(parts_f[0], parts_f[1], parts_f[2])
                d_to = date(parts_t[0], parts_t[1], parts_t[2])
                if d_from <= d_to:
                    return d_from, d_to, period
        except (ValueError, AttributeError):
            pass
        # fallback
        return first_day_of_month(today), last_day_of_month(today), "custom"
    # this_month (default)
    return first_day_of_month(today), last_day_of_month(today), period


def category_usage_counts(category) -> dict[str, int]:
    from finance.models import InstallmentPlan, RecurringBill

    return {
        "transactions": category.transactions.count(),
        "installment_plans": InstallmentPlan.objects.filter(category=category).count(),
        "recurring_bills": RecurringBill.objects.filter(category=category).count(),
    }
