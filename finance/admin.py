from django.contrib import admin

from .models import (
    Category,
    InstallmentPlan,
    Notification,
    RecurringBill,
    RecurringBillOccurrence,
    Transaction,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "kind", "color", "sort_order")
    list_filter = ("kind",)
    search_fields = ("name", "user__email")


class TransactionInline(admin.TabularInline):
    model = Transaction
    fk_name = "installment_plan"
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "total_amount", "installment_count", "first_due_date")
    search_fields = ("title", "user__email")
    inlines = [TransactionInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "user",
        "amount",
        "transaction_type",
        "occurred_on",
        "category",
    )
    list_filter = ("transaction_type", "is_recurring")
    search_fields = ("description", "user__email")
    date_hierarchy = "occurred_on"
    raw_id_fields = ("user", "category", "installment_plan")


class RecurringOccurrenceInline(admin.TabularInline):
    model = RecurringBillOccurrence
    extra = 0


@admin.register(RecurringBill)
class RecurringBillAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "amount", "due_day", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "user__email")
    inlines = [RecurringOccurrenceInline]


@admin.register(RecurringBillOccurrence)
class RecurringBillOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("recurring_bill", "year", "month", "is_paid", "paid_at")
    list_filter = ("is_paid",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "read_at", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "user__email")
