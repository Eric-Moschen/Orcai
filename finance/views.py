from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from finance.forms import CategoryForm, RecurringBillForm, TransactionForm
from finance.mixins import UserScopedMixin
from finance.models import Category, RecurringBill, Transaction, TransactionType
from finance.services.installments import create_installment_plan_with_transactions
from finance.services.period import category_usage_counts, resolve_period_from_get
from finance.services.recurring import (
    due_date_for_month,
    get_or_create_occurrence,
    mark_occurrence_paid,
    mark_occurrence_unpaid,
)
from finance.services.suggestions import suggest_category_for_description


class CategoryListView(UserScopedMixin, ListView):
    model = Category
    context_object_name = "categories"
    template_name = "finance/category_list.html"


class CategoryCreateView(UserScopedMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Categoria criada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:category_list")


class CategoryUpdateView(UserScopedMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "finance/category_form.html"
    pk_url_kwarg = "pk"

    def form_valid(self, form):
        messages.success(self.request, "Categoria atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:category_list")


class CategoryDeleteView(UserScopedMixin, DeleteView):
    model = Category
    template_name = "finance/category_confirm_delete.html"
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("finance:category_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        counts = category_usage_counts(self.object)
        total = sum(counts.values())
        if total:
            messages.error(
                request,
                "Não é possível excluir: a categoria está em uso. "
                f"Transações: {counts['transactions']}, "
                f"parcelamentos: {counts['installment_plans']}, "
                f"contas fixas: {counts['recurring_bills']}. "
                "Reatribua ou remova esses registros antes.",
            )
            return HttpResponseRedirect(reverse("finance:category_list"))
        messages.success(request, "Categoria excluída.")
        return super().delete(request, *args, **kwargs)


class TransactionListView(UserScopedMixin, ListView):
    model = Transaction
    context_object_name = "transactions"
    template_name = "finance/transaction_list.html"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("category", "installment_plan")
            .order_by("-occurred_on", "-pk")
        )
        df, dt, period = resolve_period_from_get(self.request.GET)
        self._filter_date_from = df
        self._filter_date_to = dt
        self._period_key = period
        qs = qs.filter(occurred_on__gte=df, occurred_on__lte=dt)
        cat = self.request.GET.get("category")
        if cat and str(cat).isdigit():
            qs = qs.filter(category_id=int(cat))
        tt = self.request.GET.get("type")
        if tt in (TransactionType.INCOME, TransactionType.EXPENSE):
            qs = qs.filter(transaction_type=tt)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(description__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_date_from"] = self._filter_date_from
        ctx["filter_date_to"] = self._filter_date_to
        ctx["period"] = self._period_key
        ctx["filter_category"] = self.request.GET.get("category") or ""
        ctx["filter_type"] = self.request.GET.get("type") or ""
        ctx["filter_q"] = self.request.GET.get("q") or ""
        ctx["category_choices"] = Category.objects.filter(user=self.request.user).order_by(
            "sort_order", "name"
        )
        p = self.request.GET.copy()
        p.pop("page", None)
        ctx["qs_nopage"] = urlencode(p)
        return ctx


class TransactionCreateView(UserScopedMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "finance/transaction_form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        kw["is_create"] = True
        return kw

    def get_initial(self):
        initial = super().get_initial()
        last = self.request.session.get("last_tx") or {}
        if last.get("transaction_type") in (TransactionType.INCOME, TransactionType.EXPENSE):
            initial.setdefault("transaction_type", last["transaction_type"])
        if last.get("category_id"):
            initial.setdefault("category", last["category_id"])
        if "is_recurring" in last:
            initial.setdefault("is_recurring", last["is_recurring"])
        desc = (self.request.GET.get("description") or "").strip()
        if desc:
            initial["description"] = desc
            tx_type = initial.get("transaction_type") or TransactionType.EXPENSE
            suggested = suggest_category_for_description(self.request.user, desc, tx_type)
            if suggested:
                initial["category"] = suggested
        return initial

    def _store_session_defaults(self, data) -> None:
        cat = data.get("category")
        self.request.session["last_tx"] = {
            "transaction_type": str(data.get("transaction_type") or ""),
            "category_id": cat.pk if cat else None,
            "is_recurring": bool(data.get("is_recurring")),
        }

    def form_valid(self, form):
        data = form.cleaned_data
        if data.get("is_installment"):
            create_installment_plan_with_transactions(
                user=self.request.user,
                title=(data["description"] or "Parcelado")[:200],
                description=data.get("notes") or "",
                category=data["category"],
                total_amount=data["amount"],
                installment_count=int(data["installment_count"]),
                first_due_date=data["occurred_on"],
                interval_months=1,
            )
            messages.success(
                self.request,
                f"Parcelamento criado: {data['installment_count']} parcelas.",
            )
            self._store_session_defaults({**data, "transaction_type": TransactionType.EXPENSE})
            return redirect(self.get_success_url())
        form.instance.user = self.request.user
        self._store_session_defaults(data)
        messages.success(self.request, "Transação registrada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:transaction_list")


class TransactionUpdateView(UserScopedMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "finance/transaction_form.html"
    pk_url_kwarg = "pk"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        kw["is_create"] = False
        return kw

    def form_valid(self, form):
        messages.success(self.request, "Transação atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:transaction_list")


class TransactionDeleteView(UserScopedMixin, DeleteView):
    model = Transaction
    template_name = "finance/transaction_confirm_delete.html"
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("finance:transaction_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        from finance.models import RecurringBillOccurrence

        if RecurringBillOccurrence.objects.filter(transaction_id=self.object.pk).exists():
            messages.error(
                request,
                "Esta transação está vinculada a uma conta fixa. "
                "Desmarque o pagamento em Contas fixas antes de excluir.",
            )
            return HttpResponseRedirect(reverse("finance:transaction_list"))
        messages.success(request, "Transação excluída.")
        return super().delete(request, *args, **kwargs)


class RecurringBillListView(UserScopedMixin, ListView):
    model = RecurringBill
    context_object_name = "bills"
    template_name = "finance/recurring_list.html"
    paginate_by = 50

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("category")
            .order_by("due_day", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        y, m = today.year, today.month
        ctx["today"] = today
        ctx["bill_year"] = y
        ctx["bill_month"] = m
        for b in ctx["bills"]:
            occ = get_or_create_occurrence(b, y, m)
            b.current_occ = occ
            b.due_this_month = due_date_for_month(b, y, m)
            delta = (b.due_this_month - today).days
            b.days_until = delta
            b.overdue_days = -delta if delta < 0 else 0
        upcoming = []
        active_all = (
            RecurringBill.objects.filter(user=self.request.user, is_active=True)
            .select_related("category")
            .order_by("due_day", "name")
        )
        for b in active_all:
            occ = get_or_create_occurrence(b, y, m)
            b.current_occ = occ
            b.due_this_month = due_date_for_month(b, y, m)
            delta = (b.due_this_month - today).days
            b.days_until = delta
            if not occ.is_paid:
                upcoming.append(b)
        upcoming.sort(key=lambda x: (x.days_until, x.due_day))
        ctx["upcoming_bills"] = upcoming[:12]
        p = self.request.GET.copy()
        p.pop("page", None)
        ctx["qs_nopage"] = urlencode(p)
        return ctx


class RecurringBillCreateView(UserScopedMixin, CreateView):
    model = RecurringBill
    form_class = RecurringBillForm
    template_name = "finance/recurring_form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Conta fixa criada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:recurring_list")


class RecurringBillUpdateView(UserScopedMixin, UpdateView):
    model = RecurringBill
    form_class = RecurringBillForm
    template_name = "finance/recurring_form.html"
    pk_url_kwarg = "pk"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["user"] = self.request.user
        return kw

    def form_valid(self, form):
        messages.success(self.request, "Conta fixa atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("finance:recurring_list")


class RecurringBillDeleteView(UserScopedMixin, DeleteView):
    model = RecurringBill
    template_name = "finance/recurring_confirm_delete.html"
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("finance:recurring_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Conta fixa excluída.")
        return super().delete(request, *args, **kwargs)


def _post_year_month(request, default):
    try:
        y = int(request.POST.get("year") or default.year)
        m = int(request.POST.get("month") or default.month)
    except (TypeError, ValueError):
        return default.year, default.month
    m = max(1, min(12, m))
    return y, m


class RecurringMarkPaidView(LoginRequiredMixin, View):
    def post(self, request, pk):
        bill = get_object_or_404(RecurringBill, pk=pk, user=request.user)
        today = timezone.localdate()
        y, m = _post_year_month(request, today)
        mark_occurrence_paid(bill, y, m)
        messages.success(request, f'"{bill.name}" marcada como paga ({m:02d}/{y}).')
        if request.POST.get("origin") == "dashboard":
            return redirect("dashboard:home")
        return redirect("finance:recurring_list")


class RecurringUnpayView(LoginRequiredMixin, View):
    def post(self, request, pk):
        bill = get_object_or_404(RecurringBill, pk=pk, user=request.user)
        today = timezone.localdate()
        y, m = _post_year_month(request, today)
        mark_occurrence_unpaid(bill, y, m)
        messages.info(request, f'Pagamento de "{bill.name}" desfeito ({m:02d}/{y}).')
        if request.POST.get("origin") == "dashboard":
            return redirect("dashboard:home")
        return redirect("finance:recurring_list")
