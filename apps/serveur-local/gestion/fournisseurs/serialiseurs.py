"""Sérialiseurs DRF du module Fournisseurs / Achats."""

from decimal import Decimal
from rest_framework import serializers

from gestion.fournisseurs.models import (
    BonCommande,
    Fournisseur,
    LigneBonCommande,
    LigneReception,
    ReceptionBonCommande,
    StatutBonCommande,
)


# ─── Fournisseur ─────────────────────────────────────────────────────────────


class FournisseurSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = Fournisseur
        fields = [
            "id", "code", "nom", "contact_principal", "telephone", "email",
            "adresse", "ville", "pays",
            "numero_agrement", "delai_livraison_jours", "conditions_paiement",
            "actif", "notes", "cree_le", "modifie_le",
        ]
        read_only_fields = ["id", "cree_le", "modifie_le"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Le code fournisseur est obligatoire.")
        return value


# ─── Lignes ──────────────────────────────────────────────────────────────────


class LigneBonCommandeSerialiseur(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(source="medicament.nom", read_only=True)
    quantite_restante = serializers.IntegerField(read_only=True)

    class Meta:
        model = LigneBonCommande
        fields = [
            "id", "medicament", "medicament_nom",
            "quantite_commandee", "quantite_recue", "quantite_restante",
            "prix_unitaire_ht", "taux_tva", "notes",
        ]
        read_only_fields = ["id", "quantite_recue", "quantite_restante", "medicament_nom"]


class LigneReceptionSerialiseur(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(
        source="ligne_bon_commande.medicament.nom", read_only=True
    )

    class Meta:
        model = LigneReception
        fields = [
            "id", "ligne_bon_commande", "medicament_nom", "lot",
            "quantite_recue", "numero_lot", "date_peremption",
            "prix_achat_unitaire",
        ]
        read_only_fields = ["id", "lot", "medicament_nom"]


# ─── Bon de commande ────────────────────────────────────────────────────────


class BonCommandeSerialiseur(serializers.ModelSerializer):
    lignes = LigneBonCommandeSerialiseur(many=True, read_only=True)
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = BonCommande
        fields = [
            "id", "numero", "fournisseur", "fournisseur_nom",
            "statut", "statut_libelle",
            "date_commande", "date_livraison_prevue",
            "total_ht", "total_tva", "total_ttc",
            "cree_par", "envoye_le", "cloture_le", "annule_le", "motif_annulation",
            "notes", "cree_le", "modifie_le",
            "lignes",
        ]
        read_only_fields = [
            "id", "numero", "statut", "statut_libelle",
            "total_ht", "total_tva", "total_ttc",
            "envoye_le", "cloture_le", "annule_le",
            "cree_par", "cree_le", "modifie_le",
        ]


class CreerBonCommandeSerialiseur(serializers.Serializer):
    """Payload de création : fournisseur + lignes."""

    class LigneEntree(serializers.Serializer):
        medicament_id = serializers.UUIDField()
        quantite = serializers.IntegerField(min_value=1)
        prix_unitaire_ht = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
        taux_tva = serializers.DecimalField(
            max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"),
            required=False, default=Decimal("0.00"),
        )
        notes = serializers.CharField(required=False, allow_blank=True, default="")

    fournisseur_id = serializers.UUIDField()
    date_livraison_prevue = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lignes = LigneEntree(many=True)


class ReceptionnerBonCommandeSerialiseur(serializers.Serializer):
    class LigneEntree(serializers.Serializer):
        ligne_bc_id = serializers.UUIDField(required=False)
        quantite_recue = serializers.IntegerField(min_value=1)
        numero_lot = serializers.CharField(max_length=60)
        date_peremption = serializers.DateField()
        prix_achat_unitaire = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            min_value=Decimal("0"),
            required=False,
            default=Decimal("0.00"),
        )

        def to_internal_value(self, data):
            data = data.copy()
            if not data.get("ligne_bc_id") and data.get("ligne_id"):
                data["ligne_bc_id"] = data["ligne_id"]
            return super().to_internal_value(data)

    numero_bordereau = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lignes = LigneEntree(many=True)


# ─── Réception ─────────────────────────────────────────────────────────────


class ReceptionBonCommandeSerialiseur(serializers.ModelSerializer):
    lignes = LigneReceptionSerialiseur(many=True, read_only=True)
    bon_commande_numero = serializers.CharField(source="bon_commande.numero", read_only=True)

    class Meta:
        model = ReceptionBonCommande
        fields = [
            "id", "bon_commande", "bon_commande_numero",
            "numero_bordereau", "date_reception", "recu_par",
            "notes", "cree_le", "lignes",
        ]
        read_only_fields = ["id", "cree_le", "bon_commande_numero"]
