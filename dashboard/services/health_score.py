from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from users.models import UserProfile

def persist_health_score(user, score: int) -> None:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.financial_health_score = score
    profile.financial_health_score_updated_at = timezone.now()
    profile.save(
        update_fields=[
            "financial_health_score",
            "financial_health_score_updated_at",
        ]
    )

def compute_financial_health_score(
    *,
    balance: Decimal,
    income: Decimal,
    expense: Decimal,
    prev_expense: Decimal,
    top_category_share: float | None,
) -> int:

    D = Decimal
    score = D('50')

    # Saldo
    if balance > 0:
        base = income if income > 0 else (expense if expense > 0 else D('1'))
        ratio = balance / base
        inc = ratio * D('10')
        if inc > D('25'):
            inc = D('25')
        score += inc

    elif balance < 0:
        base = expense if expense > 0 else D('1')
        ratio = abs(balance) / base
        dec = ratio * D('25')
        if dec > D('30'):
            dec = D('30')
        score -= dec

    # Taxa de poupança
    if income > 0:
        sr = (income - expense) / income
        adj = sr * D('25')
        if adj > D('20'):
            adj = D('20')
        if adj < D('-15'):
            adj = D('-15')
        score += adj
    elif expense > 0:
        score -= D('15')

    # Tendência
    if prev_expense > 0 and expense > 0:
        delta = (expense - prev_expense) / prev_expense
        if delta <= D('-0.05'):
            score += D('8')
        elif delta >= D('0.25'):
            score -= D('10')

    # Concentração
    if top_category_share is not None:
        if Decimal(str(top_category_share)) > D('0.65'):
            score -= D('8')

    # Clamp + arredondamento correto
    score = score.quantize(D('1'), rounding=ROUND_HALF_UP)

    return max(0, min(100, int(score)))