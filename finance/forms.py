from decimal import Decimal

from django import forms
from django.db.models import Q

from finance.models import Category, CategoryKind, RecurringBill, Transaction, TransactionType

_INPUT = (
    "mt-1 w-full rounded-lg border border-white/10 bg-[#0B0B12] px-3 py-2 text-white "
    "outline-none focus:ring-2 focus:ring-skyfi"
)
_CHECK = "h-4 w-4 rounded border-white/20 bg-night text-orchid focus:ring-skyfi"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "kind", "color", "sort_order")
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT}),
            "kind": forms.Select(attrs={"class": _INPUT}),
            "color": forms.TextInput(
                attrs={"class": _INPUT, "type": "color", "style": "height:2.75rem;padding:0.25rem"}
            ),
            "sort_order": forms.NumberInput(attrs={"class": _INPUT}),
        }


class TransactionForm(forms.ModelForm):
    is_installment = forms.BooleanField(
        label="Parcelar compra",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": _CHECK}),
    )
    installment_count = forms.IntegerField(
        label="Número de parcelas",
        required=False,
        min_value=2,
        max_value=120,
        initial=2,
        widget=forms.NumberInput(attrs={"class": _INPUT, "min": 2, "max": 120}),
    )

    class Meta:
        model = Transaction
        fields = (
            "description",
            "amount",
            "transaction_type",
            "category",
            "occurred_on",
            "is_recurring",
            "notes",
        )
        widgets = {
            "description": forms.TextInput(attrs={"class": _INPUT}),
            "amount": forms.NumberInput(attrs={"class": _INPUT, "step": "0.01", "min": "0.01"}),
            "transaction_type": forms.Select(attrs={"class": _INPUT, "id": "id_transaction_type"}),
            "category": forms.Select(attrs={"class": _INPUT, "id": "id_category"}),
            "occurred_on": forms.DateInput(attrs={"class": _INPUT, "type": "date"}),
            "is_recurring": forms.CheckboxInput(attrs={"class": _CHECK}),
            "notes": forms.Textarea(attrs={"class": _INPUT + " min-h-[80px]", "rows": 3}),
        }

    def __init__(self, *args, user=None, is_create: bool = True, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).order_by(
                "sort_order", "name"
            )
            self.fields["category"].required = False
        if not is_create:
            self.fields.pop("is_installment", None)
            self.fields.pop("installment_count", None)

    def clean_amount(self):
        value: Decimal = self.cleaned_data["amount"]
        if value <= 0:
            raise forms.ValidationError("O valor deve ser maior que zero.")
        return value

    def _category_allowed(self, category: Category | None, tx_type: str) -> bool:
        if category is None:
            return True
        if category.kind == CategoryKind.BOTH:
            return True
        if tx_type == TransactionType.INCOME:
            return category.kind == CategoryKind.INCOME
        return category.kind == CategoryKind.EXPENSE

    def clean(self):
        data = super().clean()
        tx_type = data.get("transaction_type")
        category = data.get("category")
        if tx_type and category and not self._category_allowed(category, tx_type):
            raise forms.ValidationError(
                "A categoria selecionada não é compatível com o tipo da transação."
            )
        is_inst = data.get("is_installment")
        count = data.get("installment_count")
        if is_inst:
            if tx_type != TransactionType.EXPENSE:
                raise forms.ValidationError("Parcelamento aplica-se apenas a despesas.")
            if not category:
                raise forms.ValidationError("Selecione uma categoria para parcelar.")
            if not count or count < 2:
                raise forms.ValidationError("Informe pelo menos 2 parcelas.")
        inst = getattr(self.instance, "installment_plan_id", None)
        if inst and tx_type != TransactionType.EXPENSE:
            raise forms.ValidationError("Transações parceladas devem permanecer como despesa.")
        return data


class RecurringBillForm(forms.ModelForm):
    class Meta:
        model = RecurringBill
        fields = (
            "name",
            "amount",
            "due_day",
            "category",
            "is_active",
            "auto_create_transaction",
            "notes",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT}),
            "amount": forms.NumberInput(attrs={"class": _INPUT, "step": "0.01", "min": "0.01"}),
            "due_day": forms.NumberInput(attrs={"class": _INPUT, "min": 1, "max": 31}),
            "category": forms.Select(attrs={"class": _INPUT}),
            "is_active": forms.CheckboxInput(attrs={"class": _CHECK}),
            "auto_create_transaction": forms.CheckboxInput(attrs={"class": _CHECK}),
            "notes": forms.Textarea(attrs={"class": _INPUT + " min-h-[80px]", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user).filter(
                Q(kind=CategoryKind.EXPENSE) | Q(kind=CategoryKind.BOTH)
            ).order_by("sort_order", "name")

    def clean_amount(self):
        value: Decimal = self.cleaned_data["amount"]
        if value <= 0:
            raise forms.ValidationError("O valor deve ser maior que zero.")
        return value
