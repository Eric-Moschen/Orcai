from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuário do Orçai — autenticação e isolamento de dados por conta."""

    email = models.EmailField("e-mail", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def save(self, *args, **kwargs):
        # Mantém username alinhado ao e-mail para login único e createsuperuser simples.
        if self.email:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email or self.username


class UserProfile(models.Model):
    """Preferências e cache leve para insights (ex.: último score calculado)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    weekly_summary_enabled = models.BooleanField("resumo semanal por e-mail", default=True)
    monthly_summary_enabled = models.BooleanField("resumo mensal", default=True)
    financial_health_score = models.PositiveSmallIntegerField(
        "último score de saúde financeira (0–100)",
        null=True,
        blank=True,
    )
    financial_health_score_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self) -> str:
        return f"Perfil de {self.user}"
