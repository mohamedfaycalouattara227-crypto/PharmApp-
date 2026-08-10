"""
gestion/catalogue/serialiseurs.py
Sérialiseurs DRF pour le catalogue.

CORRECTION étape 4 :
  - CategorieProduitSerialiseur : code_classification → code (champ inexistant corrigé)
  - MedicamentSerialiseur : ajout aliases dci/forme pour compatibilité frontend
    + ajout prix_reglemente, prix_reference, hors_nomenclature
    + filtre DCI dans VueMedicament (voir vues.py)
"""

from rest_framework import serializers
from gestion.catalogue.models import CategorieProduit, Medicament, Lot


class CategorieProduitSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = CategorieProduit
        fields = ["id", "nom", "description", "code", "est_active", "cree_le"]
        read_only_fields = ["id", "cree_le"]


class MedicamentSerialiseur(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True, default=None)
    # Aliases pour compatibilité frontend (CDC §4.2)
    dci = serializers.CharField(
        source="denomination_commune_internationale", read_only=True, allow_null=True
    )
    forme = serializers.CharField(
        source="forme_pharmaceutique", read_only=True, allow_null=True
    )
    # prix_vente = alias de prix_public pour le POS
    prix_vente = serializers.DecimalField(
        source="prix_public", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Medicament
        fields = [
            "id", "nom",
            "denomination_commune_internationale", "dci",
            "categorie", "categorie_nom",
            "forme_pharmaceutique", "forme",
            "dosage", "conditionnement",
            "code_cis", "code_barre",
            "fabricant", "pays_origine",
            "prix_public", "prix_vente",
            "prix_min_autorise", "prix_max_autorise",
            "taux_remise_max",
            # Étape 4
            "prix_reglemente", "prix_reference", "hors_nomenclature",
            "necessite_ordonnance", "est_produit_controle",
            "seuil_alerte_stock", "seuil_rupture_stock",
            "stock_total_disponible", "est_actif", "est_en_alerte_stock",
            "cree_le", "modifie_le",
        ]
        read_only_fields = [
            "id", "dci", "forme", "prix_vente",
            "stock_total_disponible", "est_en_alerte_stock",
            "cree_le", "modifie_le",
        ]

    def validate(self, attrs):
        """Si prix_reglemente=True, prix_reference est obligatoire."""
        prix_reglemente = attrs.get("prix_reglemente", getattr(self.instance, "prix_reglemente", False))
        prix_reference = attrs.get("prix_reference", getattr(self.instance, "prix_reference", None))
        if prix_reglemente and not prix_reference:
            raise serializers.ValidationError({
                "prix_reference": "Le prix de référence est obligatoire quand le prix est réglementé."
            })
        return attrs


class LotSerialiseur(serializers.ModelSerializer):
    medicament_nom = serializers.CharField(source="medicament.nom", read_only=True)

    class Meta:
        model = Lot
        fields = [
            "id", "medicament", "medicament_nom",
            "numero_lot", "numero_lot_interne",
            "quantite_initiale", "quantite_disponible",
            "prix_achat_unitaire", "date_fabrication", "date_peremption",
            "emplacement_stockage", "fournisseur", "bon_commande",
            "est_actif", "notes",
            "est_perime", "cree_le",
        ]
        read_only_fields = ["id", "est_perime", "cree_le"]
