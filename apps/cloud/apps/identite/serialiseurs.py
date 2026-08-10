"""
apps/identite/serialiseurs.py
Sérialiseurs DRF pour les Officines.
"""

from rest_framework import serializers
from apps.identite.models import Officine, StatutAbonnement


class OfficineCreationSerialiseur(serializers.Serializer):
    """Valide les données de création d'une officine (endpoint admin)."""

    nom   = serializers.CharField(max_length=200, help_text="Raison sociale ou nom commercial.")
    code  = serializers.CharField(
        max_length=20,
        help_text='Code court unique. Exemple : "PHA-001".',
    )
    ville = serializers.CharField(max_length=100, required=False, default="")
    pays  = serializers.CharField(max_length=100, required=False, default="Burkina Faso")
    notes = serializers.CharField(required=False, default="", allow_blank=True)

    def validate_code(self, valeur: str) -> str:
        valeur = valeur.strip().upper()
        if not valeur:
            raise serializers.ValidationError("Le code ne peut pas être vide.")
        # NE PAS vérifier l'unicité ici — c'est le service qui lève ValueError
        # et la vue traduit en HTTP 409. Un 400 de sérialiseur serait incorrect.
        return valeur


class OfficineProvisionnementSerialiseur(serializers.Serializer):
    """
    Résultat de la création — contient la clé API complète.
    Retourné UNE SEULE FOIS au moment du provisionnement.
    """
    officine_id     = serializers.UUIDField()
    code            = serializers.CharField()
    nom             = serializers.CharField()
    cle_api         = serializers.CharField(
        help_text="Clé API complète — à stocker immédiatement. Non récupérable ensuite."
    )
    cle_api_prefixe = serializers.CharField(
        help_text="Préfixe non-secret de la clé pour identification dans les logs."
    )


class OfficineListeSerialiseur(serializers.ModelSerializer):
    """Sérialiseur de liste — n'expose jamais le hash de clé."""

    est_en_ligne = serializers.BooleanField(read_only=True)
    abonnement_actif = serializers.BooleanField(read_only=True)

    class Meta:
        model = Officine
        fields = [
            "id",
            "code",
            "nom",
            "ville",
            "pays",
            "statut_abonnement",
            "version_logiciel",
            "derniere_connexion",
            "est_en_ligne",
            "abonnement_actif",
            "cle_api_prefixe",
            "est_active",
            "cree_le",
            "mis_a_jour_le",
        ]
        read_only_fields = fields


class OfficineDetailSerialiseur(OfficineListeSerialiseur):
    """Sérialiseur détail — ajoute les notes internes."""

    class Meta(OfficineListeSerialiseur.Meta):
        fields = OfficineListeSerialiseur.Meta.fields + ["notes"]
        read_only_fields = fields


class RegenerationCleSerialiseur(serializers.Serializer):
    """Confirmation de la régénération de clé API."""

    officine_id     = serializers.UUIDField()
    code            = serializers.CharField()
    nom             = serializers.CharField()
    cle_api         = serializers.CharField(
        help_text="Nouvelle clé API complète — à stocker immédiatement. L'ancienne est invalidée."
    )
    cle_api_prefixe = serializers.CharField()
