from decimal import Decimal

from django.db import transaction

from finance.models import InstallmentPlan, Transaction, TransactionType

from .dates import add_months


def _split_installment_amounts(total: Decimal, count: int) -> list[Decimal]:
    """Divide o total em N parcelas; centavos restantes vão para a última parcela."""
    if count < 2:
        raise ValueError("count deve ser >= 2")
    cents = total.quantize(Decimal("0.01"))
    base = (cents / count).quantize(Decimal("0.01"))
    amounts = [base] * count
    diff = cents - base * count
    if diff:
        amounts[-1] = (amounts[-1] + diff).quantize(Decimal("0.01"))
    return amounts


@transaction.atomic
def create_installment_plan_with_transactions(
    *,
    user,
    title: str,
    description: str,
    category,
    total_amount: Decimal,
    installment_count: int,
    first_due_date,
    interval_months: int = 1,
) -> InstallmentPlan:
    """
    Cria um InstallmentPlan e N transações de despesa (parcelas).
    """
    if installment_count < 2:
        raise ValueError("Parcelamento requer pelo menos 2 parcelas.")
    amounts = _split_installment_amounts(total_amount, installment_count)
    plan = InstallmentPlan.objects.create(
        user=user,
        title=title,
        description=description or "",
        category=category,
        total_amount=total_amount,
        installment_count=installment_count,
        first_due_date=first_due_date,
        interval_months=interval_months,
    )
    for i, amt in enumerate(amounts, start=1):
        due = first_due_date if i == 1 else add_months(first_due_date, interval_months * (i - 1))
        Transaction.objects.create(
            user=user,
            description=f"{title} ({i}/{installment_count})",
            amount=amt,
            transaction_type=TransactionType.EXPENSE,
            category=category,
            occurred_on=due,
            is_recurring=False,
            installment_plan=plan,
            installment_number=i,
        )
    return plan
