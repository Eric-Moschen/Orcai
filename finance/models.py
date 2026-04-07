from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class CategoryKind(models.TextChoices):
    """Define se a categoria aplica a receitas, despesas ou ambos."""

    EXPENSE = "expense", _("Despesa")
    INCOME = "income", _("Receita")
    BOTH = "both", _("Ambos")


class TransactionType(models.TextChoices):
    INCOME = "income", _("Receita")
    EXPENSE = "expense", _("Despesa")


class Category(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField("nome", max_length=120)
    slug = models.SlugField(max_length=130, blank=True)
    kind = models.CharField(
        "tipo",
        max_length=16,
        choices=CategoryKind.choices,
        default=CategoryKind.EXPENSE,
    )
    color = models.CharField("cor (hex)", max_length=7, default="#6C4CF1")
    sort_order = models.PositiveSmallIntegerField("ordem", default=0)
    is_system = models.BooleanField(
        "categoria do sistema",
        default=False,
        help_text="Criada automaticamente; o usuário pode ocultar mas não excluir facilmente.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "slug"],
                name="unique_category_slug_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "kind"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                previous = Category.objects.get(pk=self.pk)
            except Category.DoesNotExist:
                previous = None
            if previous is not None and previous.name != self.name:
                self.slug = ""
        if not self.slug:
            base = (slugify(self.name) or "categoria")[:120]
            slug = base
            n = 2
            while True:
                qs = Category.objects.filter(user=self.user, slug=slug)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if not qs.exists():
                    self.slug = slug
                    break
                slug = f"{base}-{n}"
                n += 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class InstallmentPlan(models.Model):
    """Agrupa parcelas de uma mesma compra (ex.: 12x no cartão)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="installment_plans",
    )
    title = models.CharField("título", max_length=200)
    description = models.TextField("descrição", blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="installment_plans",
    )
    total_amount = models.DecimalField(
        "valor total",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    installment_count = models.PositiveSmallIntegerField(
        "número de parcelas",
        validators=[MinValueValidator(2), MaxValueValidator(120)],
    )
    first_due_date = models.DateField("vencimento da 1ª parcela")
    interval_months = models.PositiveSmallIntegerField(
        "intervalo entre parcelas (meses)",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "plano de parcelamento"
        verbose_name_plural = "planos de parcelamento"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.installment_count}x)"


class Transaction(models.Model):
    """Receita ou despesa; pode pertencer a um plano de parcelas."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    description = models.CharField("descrição", max_length=255)
    amount = models.DecimalField(
        "valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    transaction_type = models.CharField(
        "tipo",
        max_length=16,
        choices=TransactionType.choices,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    occurred_on = models.DateField("data")
    is_recurring = models.BooleanField(
        "recorrente",
        default=False,
        help_text="Indica padrão recorrente além do plano de parcelas (ex.: assinatura).",
    )
    installment_plan = models.ForeignKey(
        InstallmentPlan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="transactions",
    )
    installment_number = models.PositiveSmallIntegerField(
        "número da parcela",
        null=True,
        blank=True,
    )
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "transação"
        verbose_name_plural = "transações"
        ordering = ["-occurred_on", "-pk"]
        indexes = [
            models.Index(fields=["user", "occurred_on"]),
            models.Index(fields=["user", "transaction_type", "occurred_on"]),
        ]

    def __str__(self) -> str:
        return f"{self.description} — {self.amount}"


class RecurringBill(models.Model):
    """Conta fixa mensal (aluguel, internet, etc.)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_bills",
    )
    name = models.CharField("nome", max_length=200)
    amount = models.DecimalField(
        "valor",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    due_day = models.PositiveSmallIntegerField(
        "dia de vencimento",
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="recurring_bills",
    )
    is_active = models.BooleanField("ativa", default=True)
    auto_create_transaction = models.BooleanField(
        "gerar despesa automaticamente no mês",
        default=True,
        help_text="Se verdadeiro, um job pode criar a transação do mês (ver comando de gestão).",
    )
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conta fixa (recorrente)"
        verbose_name_plural = "contas fixas (recorrentes)"
        ordering = ["due_day", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_recurring_bill_name_per_user",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class RecurringBillOccurrence(models.Model):
    """Controle mensal: pago ou não, com vínculo opcional à transação gerada."""

    recurring_bill = models.ForeignKey(
        RecurringBill,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    is_paid = models.BooleanField("pago", default=False)
    paid_at = models.DateTimeField("pago em", null=True, blank=True)
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_occurrence",
    )

    class Meta:
        verbose_name = "ocorrência de conta fixa"
        verbose_name_plural = "ocorrências de contas fixas"
        constraints = [
            models.UniqueConstraint(
                fields=["recurring_bill", "year", "month"],
                name="unique_recurring_occurrence_per_month",
            ),
        ]
        ordering = ["-year", "-month"]

    def __str__(self) -> str:
        return f"{self.recurring_bill} — {self.year}-{self.month:02d}"


class NotificationKind(models.TextChoices):
    DUE_SOON = "due_soon", _("Vencimento próximo")
    SPENDING_SPIKE = "spending_spike", _("Gasto fora do padrão")
    FORECAST_WARNING = "forecast_warning", _("Alerta de previsão")
    WEEKLY_SUMMARY = "weekly_summary", _("Resumo semanal")
    MONTHLY_SUMMARY = "monthly_summary", _("Resumo mensal")
    INSIGHT = "insight", _("Insight automático")
    OTHER = "other", _("Outro")


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(
        "tipo",
        max_length=32,
        choices=NotificationKind.choices,
        default=NotificationKind.OTHER,
    )
    title = models.CharField("título", max_length=200)
    body = models.TextField("mensagem")
    read_at = models.DateTimeField("lida em", null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "read_at"]),
        ]

    def __str__(self) -> str:
        return self.title
