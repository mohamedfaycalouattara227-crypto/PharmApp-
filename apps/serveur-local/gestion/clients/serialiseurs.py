"""
gestion/clients/serialiseurs.py
Sérialiseurs DRF pour les clients.

ÉTAPE 5 — Restriction allergies par rôle (§7.2 CDC) :
  Le champ `allergies` est une donnée médicale sensible.
  La restriction est appliquée CÔTÉ SERVEUR dans le sérialiseur, pas uniquement dans l'UI.
  Un caissier qui inspecte la réponse API brute ne verra jamais les allergies.

  Implémentation :
    - `to_representation()` supprime allergies si l'utilisateur est < pharmacien_adjoint (niveau 4).
    - Le contexte `request` est obligatoire pour que la restriction fonctionne.
    - Si le contexte est absent (ex: gestion admin), allergies est masqué par précaution.
"""

from rest_framework import serializers
from gestion.clients.models import Client

# Niveau minimum pour voir les allergies : pharmacien_adjoint = 4
NIVEAU_MIN_ALLERGIES = 4


class ClientSerialiseur(serializers.ModelSerializer):
    nom_complet = serializers.CharField(read_only=True)
    encours_credit = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id", "prenom", "nom", "nom_complet",
            "telephone", "email", "adresse", "date_naissance",
            "type_client", "assureur", "numero_assurance",
            "taux_prise_en_charge", "credit_autorise", "plafond_credit",
            "encours_credit",
            # allergies toujours inclus dans la liste de champs pour pouvoir être retiré dynamiquement
            "allergies",
            "est_actif", "est_anonymise", "notes", "cree_le", "modifie_le",
        ]
        read_only_fields = ["id", "nom_complet", "est_anonymise", "cree_le", "modifie_le"]

    def to_representation(self, instance):
        """Masque les allergies pour les rôles < pharmacien_adjoint."""
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is None:
            # Pas de contexte request → masquage par précaution
            data.pop("allergies", None)
            return data
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            data.pop("allergies", None)
            return data
        from api.permissions import HIERARCHIE_ROLES
        niveau_user = HIERARCHIE_ROLES.get(getattr(user, "role", ""), -1)
        if niveau_user < NIVEAU_MIN_ALLERGIES:
            data.pop("allergies", None)
        return data
