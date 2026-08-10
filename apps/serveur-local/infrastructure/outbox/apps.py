from django.apps import AppConfig


class OutboxConfig(AppConfig):
    name = "infrastructure.outbox"
    label = "outbox"
    verbose_name = "Outbox transactionnelle"
    default_auto_field = "django.db.models.BigAutoField"
