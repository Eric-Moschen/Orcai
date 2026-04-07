from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from finance.models import Category, CategoryKind, TransactionType
from finance.services.installments import create_installment_plan_with_transactions
from finance.services.period import resolve_period_from_get
from finance.services.suggestions import suggest_category_for_description

User = get_user_model()


class InstallmentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "t@t.com", email="t@t.com", password="secret123"
        )
        self.cat = Category.objects.create(
            user=self.user,
            name="Compras",
            kind=CategoryKind.EXPENSE,
            color="#6C4CF1",
        )

    def test_split_totals_match(self):
        plan = create_installment_plan_with_transactions(
            user=self.user,
            title="TV",
            description="",
            category=self.cat,
            total_amount=Decimal("100.01"),
            installment_count=3,
            first_due_date=date(2026, 4, 10),
            interval_months=1,
        )
        txs = plan.transactions.order_by("installment_number")
        self.assertEqual(txs.count(), 3)
        s = sum(t.amount for t in txs)
        self.assertEqual(s, Decimal("100.01"))


class PeriodResolveTests(TestCase):
    def test_this_month_key(self):
        from django.http import QueryDict

        d0, d1, key = resolve_period_from_get(QueryDict())
        self.assertEqual(key, "this_month")
        self.assertLessEqual(d0, d1)


class SuggestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "s@s.com", email="s@s.com", password="secret123"
        )
        self.cat = Category.objects.create(
            user=self.user,
            name="Mercado",
            kind=CategoryKind.EXPENSE,
        )

    def test_suggests_from_history(self):
        from datetime import date

        from finance.models import Transaction

        Transaction.objects.create(
            user=self.user,
            description="Compra no mercado central",
            amount=Decimal("50.00"),
            transaction_type=TransactionType.EXPENSE,
            category=self.cat,
            occurred_on=date(2026, 1, 5),
        )
        sid = suggest_category_for_description(
            self.user, "mercado", TransactionType.EXPENSE
        )
        self.assertEqual(sid, self.cat.pk)
