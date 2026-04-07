from django.contrib.auth.mixins import LoginRequiredMixin


class UserScopedMixin(LoginRequiredMixin):
    """Garante queryset filtrado pelo usuário autenticado."""

    user_field = "user"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(**{self.user_field: self.request.user})
