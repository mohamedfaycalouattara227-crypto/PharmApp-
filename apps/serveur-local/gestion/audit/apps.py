from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "gestion.audit"
    label = "audit"
    verbose_name = "Journal d'audit"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        DT-019 (décision 2026-08-06) : l'enregistrement des gestionnaires d'audit
        sur le bus d'événements est DÉSACTIVÉ.

        Raison : aucun appel bus.publier() n'existe dans le code de production ;
        les gestionnaires ne seraient jamais déclenchés. Les activer tout en
        conservant les appels directs ServiceAudit() dans les services métier
        produirait une double-journalisation dès que le bus serait câblé.

        Source de vérité actuelle pour le journal d'audit :
          - vente créée / annulée      → gestion/ventes/services.py  (§13)
          - ajustement de stock manuel → gestion/stocks/services.py
          - connexion réussie/échouée  → gestion/authentification/vues.py

        Pour câbler réellement le bus à l'avenir :
          1. Supprimer les appels directs ServiceAudit() dans les services concernés.
          2. Décommenter le bloc ci-dessous.
          3. Ajouter bus.publier() dans chaque service métier.
          4. Fermer DT-019 avec preuve (tests automatisés).

        # from infrastructure.bus_evenements.bus import obtenir_bus
        # from gestion.audit.services import enregistrer_gestionnaires_audit
        # enregistrer_gestionnaires_audit(obtenir_bus())
        """
        import logging
        logging.getLogger("pharmapp.audit").debug(
            "DT-019 : enregistrement gestionnaires bus audit désactivé volontairement."
        )
