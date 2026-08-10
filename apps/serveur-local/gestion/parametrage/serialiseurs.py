"""
gestion/parametrage/serialiseurs.py
Sérialiseur DRF pour le singleton Paramétrage.
"""

from rest_framework import serializers
from gestion.parametrage.models import Parametrage


class ParametrageSerialiseur(serializers.ModelSerializer):
    """
    Lecture/écriture partielle du paramétrage (PATCH conseillé pour les mises à jour).
    Le champ `logo` est en lecture seule ici ; l'upload se fait via un endpoint
    multipart dédié (prévu en étape ultérieure).
    """

    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Parametrage
        fields = [
            "id",
            "nom_pharmacie",
            "adresse",
            "telephone",
            "email",
            "ville",
            "numero_agrement",
            "logo",
            "logo_url",
            "devise",
            "format_numerotation",
            "seuil_alerte_stock_jours",
            "seuil_peremption_jours",
            "type_imprimante",
            "timeout_inactivite_minutes",
            "nb_tentatives_connexion_max",
            "modifie_le",
        ]
        read_only_fields = ["id", "modifie_le", "logo", "logo_url"]

    def get_logo_url(self, obj: Parametrage) -> str | None:
        if obj.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None
