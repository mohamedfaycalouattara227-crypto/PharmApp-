"""
gestion/ventes/serialiseurs.py
Sérialiseurs DRF pour les ventes et clôtures de caisse.
"""

from rest_framework import serializers

from gestion.ventes.models import Vente, LigneVente, ClotureCaisse


class Medicament(serializers.Serializer):
    """Représentation minimale d'un médicament dans le contexte vente."""
    id = serializers.UUIDField()
    nom = serializers.CharField()
    prix_public = serializers.DecimalField(max_digits=12, decimal_places=2)
    necessite_ordonnance = serializers.BooleanField()


class LigneVenteSerialiseur(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(
        source="medicament.nom", read_only=True, default=None
    )

    class Meta:
        model = LigneVente
        fields = [
            "id", "lot", "medicament", "medicament_nom",
            "quantite", "prix_unitaire", "taux_remise", "montant_total",
        ]


class VenteSerialiseur(serializers.ModelSerializer):
    lignes = LigneVenteSerialiseur(many=True, read_only=True)
    vendeur_nom = serializers.CharField(source="vendeur.nom_complet", read_only=True)
    client_nom = serializers.SerializerMethodField()

    class Meta:
        model = Vente
        fields = [
            "id", "numero", "statut", "mode_paiement",
            "montant_total", "montant_encaisse", "montant_rendu",
            "vendeur", "vendeur_nom", "client", "client_nom",
            "ordonnance", "reference_mobile_money",
            "vente_origine",
            "cree_le", "lignes",
        ]
        read_only_fields = ["id", "numero", "montant_rendu", "cree_le", "vente_origine"]

    def get_client_nom(self, obj):
        return obj.client.nom_complet if obj.client else None


class VenteCreationSerialiseur(serializers.Serializer):
    """Sérialiseur pour la création d'une vente."""
    panier = serializers.ListField(child=serializers.DictField())
    mode_paiement = serializers.ChoiceField(choices=[
        "especes", "mobile_money", "assurance", "credit", "cheque"
    ])
    montant_encaisse = serializers.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    client_id = serializers.UUIDField(required=False, allow_null=True)
    ordonnance_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_panier(self, value):
        if not value:
            raise serializers.ValidationError("Le panier ne peut pas être vide.")
        return value


class ClotureCaisseSerialiseur(serializers.ModelSerializer):
    caissier_nom = serializers.CharField(source="caissier.nom_complet", read_only=True)
    validee_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ClotureCaisse
        fields = [
            "id", "date_cloture",
            "caissier", "caissier_nom",
            "validee_par", "validee_par_nom",
            "fond_caisse_ouverture", "fond_caisse_cloture",
            "recettes_especes", "recettes_mobile_money", "recettes_assurance",
            "recettes_credit", "recettes_cheque",
            "chiffre_affaires", "nombre_ventes", "nombre_annulations",
            "ecart_caisse", "statut", "notes",
            "cree_le", "modifie_le",
        ]
        read_only_fields = ["id", "ecart_caisse", "cree_le", "modifie_le"]

    def get_validee_par_nom(self, obj) -> str | None:
        return obj.validee_par.nom_complet if obj.validee_par else None
