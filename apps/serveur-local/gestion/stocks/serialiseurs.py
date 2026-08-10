"""
gestion/stocks/serialiseurs.py
Sérialiseurs DRF pour les stocks.
"""

from rest_framework import serializers
from gestion.stocks.models import MouvementStock, AlerteStock, Inventaire, LigneInventaire


class MouvementStockSerialiseur(serializers.ModelSerializer):
    # Champs enrichis en lecture seule pour l'affichage frontend
    lot_nom          = serializers.CharField(source="lot.numero_lot",         read_only=True)
    medicament_nom   = serializers.CharField(source="lot.medicament.nom",     read_only=True)
    medicament_id    = serializers.UUIDField(source="lot.medicament.id",      read_only=True)
    effectue_par_nom = serializers.CharField(source="effectue_par.nom_complet", read_only=True, default="")
    type_mouvement_libelle = serializers.CharField(
        source="get_type_mouvement_display", read_only=True
    )

    class Meta:
        model = MouvementStock
        fields = [
            "id",
            "lot",
            "lot_nom",
            "medicament_id",
            "medicament_nom",
            "type_mouvement",
            "type_mouvement_libelle",
            "quantite",
            "quantite_avant",
            "quantite_apres",
            "motif",
            "reference_document",
            "effectue_par",
            "effectue_par_nom",
            "cree_le",
        ]
        read_only_fields = ["id", "cree_le"]


class AlerteStockSerialiseur(serializers.ModelSerializer):
    medicament_nom   = serializers.CharField(source="medicament.nom",    read_only=True)
    medicament_id    = serializers.UUIDField(source="medicament.id",      read_only=True)
    niveau_libelle   = serializers.CharField(source="get_niveau_display", read_only=True)

    class Meta:
        model = AlerteStock
        fields = [
            "id",
            "medicament",
            "medicament_id",
            "medicament_nom",
            "niveau",
            "niveau_libelle",
            "stock_au_moment_alerte",
            "seuil_depasse",
            "est_resolue",
            "resolue_le",
            "cree_le",
        ]
        read_only_fields = ["id", "cree_le"]


class LigneInventaireSerialiseur(serializers.ModelSerializer):
    class Meta:
        model = LigneInventaire
        fields = [
            "id",
            "lot",
            "quantite_systeme",
            "quantite_comptee",
            "ecart",
            "ecart_pourcent",
            "notes",
        ]


class InventaireSerialiseur(serializers.ModelSerializer):
    lignes = LigneInventaireSerialiseur(many=True, read_only=True)

    class Meta:
        model = Inventaire
        fields = [
            "id",
            "reference",
            "statut",
            "demarre_par",
            "valide_par",
            "cree_le",
            "termine_le",
            "valide_le",
            "notes",
            "lignes",
        ]
        read_only_fields = ["id", "cree_le"]
