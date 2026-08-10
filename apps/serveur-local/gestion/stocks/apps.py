from django.apps import AppConfig


class StocksConfig(AppConfig):
    name = "gestion.stocks"
    label = "stocks"
    verbose_name = "Gestion des stocks"
    default_auto_field = "django.db.models.BigAutoField"
