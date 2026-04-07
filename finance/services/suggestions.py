from django.db.models import Q

from finance.models import CategoryKind, Transaction, TransactionType


def suggest_category_for_description(
    user,
    description: str,
    transaction_type: str,
) -> int | None:
    """
    Retorna o ID da categoria mais recente usada com descrição semelhante.
    Comparação simples por substring (case-insensitive).
    """
    if not description or len(description.strip()) < 2:
        return None
    needle = description.strip().lower()
    qs = Transaction.objects.filter(user=user).exclude(category__isnull=True)
    if transaction_type == TransactionType.INCOME:
        qs = qs.filter(transaction_type=TransactionType.INCOME).filter(
            Q(category__kind=CategoryKind.INCOME) | Q(category__kind=CategoryKind.BOTH)
        )
    else:
        qs = qs.filter(transaction_type=TransactionType.EXPENSE).filter(
            Q(category__kind=CategoryKind.EXPENSE) | Q(category__kind=CategoryKind.BOTH)
        )
    for tx in qs.order_by("-occurred_on", "-pk")[:200]:
        if needle in tx.description.lower() or tx.description.lower() in needle:
            return tx.category_id
    return None
