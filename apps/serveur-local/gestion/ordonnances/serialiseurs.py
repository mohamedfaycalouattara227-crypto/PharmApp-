"""
gestion/ordonnances/serialiseurs.py
Sérialiseurs DRF pour les ordonnances.

CORRECTION ÉTAPE 10 : correction des champs référencés qui n'existaient pas dans le modèle.
  Champs corrects (depuis le modèle Ordonnance) :
    id, numero_interne, client (FK), prescripteur_nom, prescripteur_etablissement,
    date_prescription, date_expiration, statut, validee_par, validee_le,
    notes, numerisee_par, cree_le, modifie_le, est_expiree, a_image
"""

from rest_framework import serializers
from gestion.ordonnances.models import Ordonnance, StatutOrdonnance


class OrdonnanceSerialiseur(serializers.ModelSerializer):
    est_expiree = serializers.BooleanField(read_only=True)
    a_image = serializers.BooleanField(read_only=True)
    client_nom = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Ordonnance
        fields = [
            "id", "numero_interne",
            "client", "client_nom",
            "prescripteur_nom", "prescripteur_etablissement",
            "date_prescription", "date_expiration",
            "statut",
            "validee_par", "validee_le",
            "notes",
            "numerisee_par",
            "a_image", "type_mime", "taille_image_octets",
            "est_expiree",
            "cree_le", "modifie_le",
        ]
        read_only_fields = [
            "id", "numero_interne", "statut", "validee_par", "validee_le",
            "numerisee_par", "a_image", "type_mime", "taille_image_octets",
            "est_expiree", "cree_le", "modifie_le",
        ]

    def get_client_nom(self, obj) -> str | None:
        if obj.client:
            return obj.client.nom_complet
        return None

    def validate(self, attrs):
        # Le statut est exposé en lecture seule par le contrat DRF, mais une
        # validation explicite protège aussi les payloads PATCH atypiques.
        if "statut" in self.initial_data:
            request = self.context.get("request")
            user = getattr(request, "user", None)
            if not getattr(user, "a_permission_role", lambda _role: False)("pharmacien_adjoint"):
                raise serializers.ValidationError({"statut": "Seul un pharmacien adjoint peut valider une ordonnance."})
        return super().validate(attrs)


class OrdonnanceUploadSerialiseur(serializers.Serializer):
    """Sérialiseur pour l'upload multipart d'une ordonnance (§10 CDC)."""
    fichier = serializers.FileField(required=True)
    client_id = serializers.UUIDField(required=False, allow_null=True)
    prescripteur_nom = serializers.CharField(required=False, default="Non renseigné", max_length=200)
    prescripteur_etablissement = serializers.CharField(required=False, allow_blank=True, default="")
    date_prescription = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
