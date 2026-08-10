"""
gestion/produits_controles/serialiseurs.py
Sérialiseurs DRF pour le registre réglementaire des produits contrôlés
(stupéfiants et psychotropes).

Note sécurité : ``patient_nom`` transite en clair dans l'API (nécessaire
pour la saisie et la consultation par le pharmacien habilité), mais est
persisté chiffré AES-256-GCM en base — la conversion est portée par
la propriété ``patient_nom`` du modèle.
L'accès au ViewSet est déjà restreint (``EstPharmacienAdjoint``).
"""

from rest_framework import serializers

from gestion.produits_controles.models import RegistreProduitControle


class RegistreProduitControleSerialiseur(serializers.ModelSerializer):
    # Exposé en clair via la propriété — jamais le champ chiffré brut.
    patient_nom = serializers.CharField(
        required=False, allow_blank=True, max_length=200
    )

    class Meta:
        model = RegistreProduitControle
        fields = [
            "id",
            "medicament", "lot",
            "numero_lot_fabricant",
            "type_mouvement",
            "quantite_mouvement", "unite",
            "stock_avant", "stock_apres",
            "ordonnance",
            "prescripteur_nom", "prescripteur_num_ordre",
            "patient_nom",
            "numero_registre_national",
            "effectue_par", "supervise_par",
            "motif", "notes_reglementaires",
            "cree_le",
        ]
        read_only_fields = ["id", "cree_le"]
        # `patient_nom_chiffre` n'est jamais exposé.
        extra_kwargs = {
            "effectue_par": {"required": False},
            "numero_lot_fabricant": {"required": False, "allow_blank": True},
            "stock_avant": {"required": False},
            "stock_apres": {"required": False},
        }

    def create(self, validated_data):
        patient_nom = validated_data.pop("patient_nom", "")
        lot = validated_data.get("lot")
        if lot is not None:
            stock_avant = validated_data.setdefault("stock_avant", lot.quantite_disponible)
            quantite = validated_data.get("quantite_mouvement", 0)
            validated_data.setdefault("stock_apres", max(0, stock_avant - quantite))
            validated_data.setdefault("numero_lot_fabricant", lot.numero_lot)
        request = self.context.get("request")
        if request is not None and getattr(request.user, "is_authenticated", False):
            validated_data.setdefault("effectue_par", request.user)
        instance = RegistreProduitControle(**validated_data)
        instance.patient_nom = patient_nom  # déclenche le chiffrement
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if "patient_nom" in validated_data:
            instance.patient_nom = validated_data.pop("patient_nom") or ""
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance
