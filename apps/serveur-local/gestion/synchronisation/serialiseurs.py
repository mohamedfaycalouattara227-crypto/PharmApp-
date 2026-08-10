"""
gestion/synchronisation/serialiseurs.py
Sérialiseurs DRF pour la synchronisation.
"""

from rest_framework import serializers
from gestion.synchronisation.models import ConflitSynchronisation, EtatSynchronisation


class EtatSynchronisationSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = EtatSynchronisation
        fields = [
            "id", "statut_connexion", "derniere_sync_reussie",
            "version_schema_locale", "version_schema_cloud",
            "cree_le", "modifie_le",
        ]
        read_only_fields = fields


class ConflitSynchronisationSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = ConflitSynchronisation
        fields = [
            "id", "modele", "id_objet",
            "donnees_locales", "donnees_cloud",
            "statut", "resolu_par", "resolu_le",
            "cree_le",
        ]
        read_only_fields = ["id", "cree_le"]
