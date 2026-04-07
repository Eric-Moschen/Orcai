from calendar import monthrange
from datetime import date

from django.db import transaction
from django.utils import timezone

from finance.models import RecurringBillOccurrence, Transaction, TransactionType


def due_date_for_month(bill, year: int, month: int) -> date:
    last = monthrange(year, month)[1]
    day = min(bill.due_day, last)
    return date(year, month, day)


def get_or_create_occurrence(bill, year: int, month: int) -> RecurringBillOccurrence:
    occ, _ = RecurringBillOccurrence.objects.get_or_create(
        recurring_bill=bill,
        year=year,
        month=month,
        defaults={"is_paid": False},
    )
    return occ


@transaction.atomic
def mark_occurrence_paid(bill, year: int, month: int) -> RecurringBillOccurrence:
    """
    Marca a ocorrência do mês como paga e cria (ou reutiliza) a transação de despesa.
    """
    occ = get_or_create_occurrence(bill, year, month)
    if occ.is_paid:
        return occ
    d = due_date_for_month(bill, year, month)
    if occ.transaction_id:
        t = occ.transaction
        t.amount = bill.amount
        t.category_id = bill.category_id
        t.occurred_on = d
        t.description = f"{bill.name} ({month:02d}/{year})"
        t.save(
            update_fields=[
                "amount",
                "category",
                "occurred_on",
                "description",
                "updated_at",
            ]
        )
    else:
        t = Transaction.objects.create(
            user=bill.user,
            description=f"{bill.name} ({month:02d}/{year})",
            amount=bill.amount,
            transaction_type=TransactionType.EXPENSE,
            category=bill.category,
            occurred_on=d,
            is_recurring=True,
        )
        occ.transaction = t
    occ.is_paid = True
    occ.paid_at = timezone.now()
    occ.save(update_fields=["is_paid", "paid_at", "transaction"])
    return occ


@transaction.atomic
def mark_occurrence_unpaid(bill, year: int, month: int) -> RecurringBillOccurrence | None:
    """Desfaz o pagamento do mês (remove vínculo e apaga a transação se existir)."""
    try:
        occ = RecurringBillOccurrence.objects.get(
            recurring_bill=bill, year=year, month=month
        )
    except RecurringBillOccurrence.DoesNotExist:
        return None
    if not occ.is_paid:
        return occ
    t = occ.transaction
    occ.is_paid = False
    occ.paid_at = None
    occ.transaction = None
    occ.save(update_fields=["is_paid", "paid_at", "transaction"])
    if t:
        t.delete()
    return occ
