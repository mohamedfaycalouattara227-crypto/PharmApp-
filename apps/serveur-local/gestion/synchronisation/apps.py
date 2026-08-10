from django.apps import AppConfig


class SynchronisationConfig(AppConfig):
    name = "gestion.synchronisation"
    label = "synchronisation"
    verbose_name = "Synchronisation"
    default_auto_field = "django.db.models.BigAutoField"
