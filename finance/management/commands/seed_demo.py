"""Cria usuário de demonstração com categorias, transações e contas fixas."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from finance.models import (
    Category,
    CategoryKind,
    RecurringBill,
    RecurringBillOccurrence,
    Transaction,
    TransactionType,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Popula o banco com um usuário demo@orcai.local e dados financeiros de exemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="demo12345",
            help="Senha do usuário demo (padrão: demo12345).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        email = "demo@orcai.local"
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Demo",
                "last_name": "Orçai",
                "is_active": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(password)
            user.save()
        action = "Criado" if created else "Atualizado"
        self.stdout.write(self.style.SUCCESS(f"{action} usuário: {email} / senha: {password}"))

        today = timezone.localdate()
        y, m = today.year, today.month
        first = date(y, m, 1)
        last_day = monthrange(y, m)[1]
        month_end = date(y, m, last_day)

        cat_moradia, _ = Category.objects.get_or_create(
            user=user,
            slug="moradia",
            defaults={
                "name": "Moradia",
                "kind": CategoryKind.EXPENSE,
                "color": "#6C4CF1",
                "sort_order": 1,
            },
        )
        cat_alim, _ = Category.objects.get_or_create(
            user=user,
            slug="alimentacao",
            defaults={
                "name": "Alimentação",
                "kind": CategoryKind.EXPENSE,
                "color": "#4DA6FF",
                "sort_order": 2,
            },
        )
        cat_trans, _ = Category.objects.get_or_create(
            user=user,
            slug="transporte",
            defaults={
                "name": "Transporte",
                "kind": CategoryKind.EXPENSE,
                "color": "#22c55e",
                "sort_order": 3,
            },
        )
        cat_sal, _ = Category.objects.get_or_create(
            user=user,
            slug="salario",
            defaults={
                "name": "Salário",
                "kind": CategoryKind.INCOME,
                "color": "#a78bfa",
                "sort_order": 0,
            },
        )

        # Salário (receita)
        Transaction.objects.get_or_create(
            user=user,
            description="Salário mensal",
            occurred_on=first,
            transaction_type=TransactionType.INCOME,
            defaults={
                "amount": Decimal("8500.00"),
                "category": cat_sal,
                "is_recurring": True,
            },
        )

        despesas = [
            ("Aluguel", Decimal("2200.00"), cat_moradia, first + timedelta(days=4)),
            ("Supermercado", Decimal("420.50"), cat_alim, first + timedelta(days=6)),
            ("Uber / transporte", Decimal("180.00"), cat_trans, first + timedelta(days=9)),
            ("Restaurante", Decimal("95.00"), cat_alim, first + timedelta(days=11)),
            ("Conta de luz", Decimal("210.00"), cat_moradia, first + timedelta(days=14)),
        ]
        for desc, amt, cat, d in despesas:
            Transaction.objects.get_or_create(
                user=user,
                description=desc,
                occurred_on=d,
                transaction_type=TransactionType.EXPENSE,
                defaults={"amount": amt, "category": cat},
            )

        bill_net, _ = RecurringBill.objects.get_or_create(
            user=user,
            name="Internet fibra",
            defaults={
                "amount": Decimal("99.90"),
                "due_day": 10,
                "category": cat_moradia,
                "is_active": True,
                "auto_create_transaction": True,
            },
        )
        occ, _ = RecurringBillOccurrence.objects.get_or_create(
            recurring_bill=bill_net,
            year=y,
            month=m,
            defaults={"is_paid": False},
        )
        if occ.transaction_id is None and bill_net.auto_create_transaction:
            t, _ = Transaction.objects.get_or_create(
                user=user,
                description=f"{bill_net.name} ({m:02d}/{y})",
                occurred_on=date(y, m, min(bill_net.due_day, last_day)),
                transaction_type=TransactionType.EXPENSE,
                defaults={
                    "amount": bill_net.amount,
                    "category": bill_net.category,
                    "is_recurring": True,
                },
            )
            occ.transaction = t
            occ.save(update_fields=["transaction"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Dados de exemplo até {month_end.isoformat()}: categorias, transações e conta fixa."
            )
        )
