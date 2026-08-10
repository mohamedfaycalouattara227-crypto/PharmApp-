from django.apps import AppConfig


class ClientsConfig(AppConfig):
    name = "gestion.clients"
    label = "clients"
    verbose_name = "Clients"
    default_auto_field = "django.db.models.BigAutoField"
