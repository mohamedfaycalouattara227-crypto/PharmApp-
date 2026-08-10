"""
apps/synchronisation/serialiseurs.py
Sérialiseurs DRF pour l'ingestion et la consultation des événements.
"""

import uuid as uuid_module
from rest_framework import serializers

from apps.synchronisation.models import EvenementSync


class EvenementEntrantSerialiseur(serializers.Serializer):
    """
    Valide le corps d'un événement entrant depuis un serveur local.

    Chaque champ a des contraintes strictes pour rejeter les payloads malformés
    avant toute persistance.
    """

    uuid = serializers.UUIDField(
        help_text="UUID v4 généré côté serveur local. Garantit l'idempotence.",
    )
    type_evenement = serializers.CharField(
        max_length=50,
        help_text="Type d'événement (ex: VENTE_CREEE, STOCK_AJUSTE…).",
    )
    version_schema = serializers.IntegerField(
        min_value=1,
        max_value=99,
        default=1,
        help_text="Version du schéma de charge_utile.",
    )
    timestamp_local = serializers.DateTimeField(
        help_text="Horodatage ISO 8601 de l'événement sur le serveur local.",
    )
    charge_utile = serializers.JSONField(
        help_text="Corps de l'événement. Structure dépend du type_evenement.",
    )

    def validate_type_evenement(self, valeur: str) -> str:
        return valeur.strip().upper()

    def validate_charge_utile(self, valeur) -> dict:
        if not isinstance(valeur, dict):
            raise serializers.ValidationError(
                "charge_utile doit être un objet JSON."
            )
        # Limite de taille : 500 Ko (protège contre les payloads géants)
        import json
        if len(json.dumps(valeur)) > 500_000:
            raise serializers.ValidationError(
                "charge_utile dépasse la limite autorisée (500 Ko)."
            )
        return valeur


class EvenementReponseSerialiseur(serializers.Serializer):
    """Réponse à l'ingestion d'un événement."""

    uuid    = serializers.UUIDField()
    statut  = serializers.CharField()
    message = serializers.CharField()


class EvenementListeSerialiseur(serializers.ModelSerializer):
    """Sérialiseur de liste des événements (console admin — Phase 4)."""

    officine_code = serializers.CharField(source="officine.code", read_only=True)

    class Meta:
        model = EvenementSync
        fields = [
            "id",
            "uuid",
            "officine_code",
            "type_evenement",
            "version_schema",
            "timestamp_local",
            "recu_le",
            "statut_traitement",
            "traite_le",
            "message_erreur",
        ]
        read_only_fields = fields
