"""
apps/synchronisation/models.py
Modèles de synchronisation Cloud PharmApp.

EvenementSync : journal immuable de tous les événements reçus
                depuis les serveurs locaux des officines.

Principes :
  - Immuabilité : aucun UPDATE sur charge_utile ou type_evenement après réception.
  - Idempotence : uuid unique — ON CONFLICT DO NOTHING côté applicatif.
  - Isolation   : chaque événement est lié à une Officine identifiée.
  - Traçabilité : statut_traitement permet de rejouer les événements échoués.
"""

import uuid as uuid_module
from django.db import models
from apps.identite.models import Officine


class StatutTraitement(models.TextChoices):
    RECU      = "recu",      "Reçu"
    EN_COURS  = "en_cours",  "En cours de traitement"
    TRAITE    = "traite",    "Traité"
    ECHEC     = "echec",     "Échec"
    IGNORE    = "ignore",    "Ignoré (type inconnu)"


class TypeEvenement(models.TextChoices):
    """
    Types d'événements supportés par l'ingestion cloud — Phase 1.
    Étendus progressivement au fil des phases.
    """
    # Ventes
    VENTE_CREEE   = "VENTE_CREEE",   "Vente créée"
    VENTE_ANNULEE = "VENTE_ANNULEE", "Vente annulée"
    AVOIR_CREE    = "AVOIR_CREE",    "Avoir créé"

    # Stock
    STOCK_AJUSTE         = "STOCK_AJUSTE",          "Stock ajusté"
    RECEPTION_LIVRAISON  = "RECEPTION_LIVRAISON",   "Réception de livraison"
    ALERTE_STOCK         = "ALERTE_STOCK",           "Alerte stock déclenchée"

    # Catalogue
    MEDICAMENT_CREE     = "MEDICAMENT_CREE",     "Médicament créé"
    MEDICAMENT_MODIFIE  = "MEDICAMENT_MODIFIE",  "Médicament modifié"
    PRIX_MODIFIE        = "PRIX_MODIFIE",         "Prix modifié"

    # Clients
    CLIENT_CREE    = "CLIENT_CREE",    "Client créé"
    CLIENT_MODIFIE = "CLIENT_MODIFIE", "Client modifié"
    CLIENT_ANONYMISE = "CLIENT_ANONYMISE", "Client anonymisé (RGPD)"

    # Système
    DEMANDE_ASSISTANCE = "DEMANDE_ASSISTANCE", "Demande d'assistance"
    ERREUR_CRITIQUE    = "ERREUR_CRITIQUE",    "Erreur critique remontée"
    HEARTBEAT          = "HEARTBEAT",          "Signal de vie"


class EvenementSync(models.Model):
    """
    Journal de tous les événements reçus depuis les serveurs locaux.

    Immuable après insertion — aucun champ métier n'est modifiable.
    Seuls statut_traitement, traite_le, et message_erreur peuvent évoluer.
    """

    uuid = models.UUIDField(
        unique=True,
        help_text="UUID généré côté serveur local. Garantit l'idempotence.",
    )
    officine = models.ForeignKey(
        Officine,
        on_delete=models.PROTECT,
        related_name="evenements_sync",
        help_text="Officine émettrice, résolue depuis la clé API.",
    )
    type_evenement = models.CharField(
        max_length=50,
        help_text="Type d'événement — détermine le traitement appliqué.",
    )
    version_schema = models.PositiveSmallIntegerField(
        default=1,
        help_text="Version du schéma de charge_utile — pour la rétrocompatibilité.",
    )
    timestamp_local = models.DateTimeField(
        help_text="Horodatage de l'événement sur le serveur local (peut différer de recu_le).",
    )
    recu_le = models.DateTimeField(
        auto_now_add=True,
        help_text="Horodatage de réception par le cloud.",
    )
    charge_utile = models.JSONField(
        help_text="Corps de l'événement — structure dépend du type_evenement.",
    )

    # ── Traitement ────────────────────────────────────────────────────────────
    statut_traitement = models.CharField(
        max_length=20,
        choices=StatutTraitement.choices,
        default=StatutTraitement.RECU,
    )
    traite_le     = models.DateTimeField(null=True, blank=True)
    message_erreur = models.TextField(blank=True)

    class Meta:
        app_label = "synchronisation"
        ordering  = ["-recu_le"]
        verbose_name = "Événement sync"
        verbose_name_plural = "Événements sync"
        indexes = [
            models.Index(fields=["uuid"]),
            models.Index(fields=["officine", "recu_le"]),
            models.Index(fields=["officine", "type_evenement"]),
            models.Index(fields=["statut_traitement"]),
            models.Index(fields=["timestamp_local"]),
        ]

    def __str__(self) -> str:
        return f"{self.type_evenement} | {self.officine.code} | {self.recu_le}"
