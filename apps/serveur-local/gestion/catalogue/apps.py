from django.apps import AppConfig


class CatalogueConfig(AppConfig):
    name = "gestion.catalogue"
    label = "catalogue"
    verbose_name = "Catalogue médicaments"
    default_auto_field = "django.db.models.BigAutoField"
