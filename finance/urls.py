from django.urls import path

from finance import views

app_name = "finance"

urlpatterns = [
    path("categorias/", views.CategoryListView.as_view(), name="category_list"),
    path("categorias/nova/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categorias/<int:pk>/editar/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("categorias/<int:pk>/excluir/", views.CategoryDeleteView.as_view(), name="category_delete"),
    path("transacoes/", views.TransactionListView.as_view(), name="transaction_list"),
    path("transacoes/nova/", views.TransactionCreateView.as_view(), name="transaction_create"),
    path("transacoes/<int:pk>/editar/", views.TransactionUpdateView.as_view(), name="transaction_update"),
    path("transacoes/<int:pk>/excluir/", views.TransactionDeleteView.as_view(), name="transaction_delete"),
    path("contas-fixas/", views.RecurringBillListView.as_view(), name="recurring_list"),
    path("contas-fixas/nova/", views.RecurringBillCreateView.as_view(), name="recurring_create"),
    path("contas-fixas/<int:pk>/editar/", views.RecurringBillUpdateView.as_view(), name="recurring_update"),
    path("contas-fixas/<int:pk>/excluir/", views.RecurringBillDeleteView.as_view(), name="recurring_delete"),
    path("contas-fixas/<int:pk>/pagar/", views.RecurringMarkPaidView.as_view(), name="recurring_mark_paid"),
    path("contas-fixas/<int:pk>/desmarcar/", views.RecurringUnpayView.as_view(), name="recurring_unpay"),
]
