from django.apps import AppConfig


class VentesConfig(AppConfig):
    name = "gestion.ventes"
    label = "ventes"
    verbose_name = "Ventes"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Attache l'action `recu` (impression / réimpression) à VueVente.
        try:
            from gestion.ventes.vues import VueVente
            from gestion.ventes.recu import brancher_action_recu
            brancher_action_recu(VueVente)
        except Exception:  # pragma: no cover — évite un ready() bloquant
            import logging
            logging.getLogger("pharmapp.ventes").exception(
                "Impossible de brancher l'action `recu` sur VueVente."
            )
