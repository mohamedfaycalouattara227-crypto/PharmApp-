"""
gestion/authentification/serialiseurs.py
Sérialiseurs DRF pour l'authentification et les utilisateurs.
"""

from rest_framework import serializers

from gestion.authentification.models import UtilisateurPharmacien, RoleUtilisateur


class UtilisateurPharmacienSerialiseur(serializers.ModelSerializer):
    """Sérialiseur complet d'un utilisateur."""

    mot_de_passe = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = UtilisateurPharmacien
        fields = [
            "id", "email", "prenom", "nom", "role",
            "telephone", "numero_ordre", "est_actif", "mot_de_passe",
            "cree_le", "modifie_le", "derniere_connexion_reussie",
        ]
        read_only_fields = ["id", "cree_le", "modifie_le", "derniere_connexion_reussie"]

    def validate_email(self, value):
        """Vérifie que l'email n'est pas déjà utilisé."""
        instance = getattr(self, "instance", None)
        qs = UtilisateurPharmacien.objects.filter(email=value)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def create(self, validated_data):
        mot_de_passe = validated_data.pop("mot_de_passe", None)
        utilisateur = UtilisateurPharmacien(**validated_data)
        if mot_de_passe:
            utilisateur.set_password(mot_de_passe)
        utilisateur.save()
        return utilisateur

    def update(self, instance, validated_data):
        mot_de_passe = validated_data.pop("mot_de_passe", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if mot_de_passe:
            instance.set_password(mot_de_passe)
        instance.save()
        return instance


# Alias de compatibilité rétroactive utilisé par les vues existantes.
UtilisateurSerialiseur = UtilisateurPharmacienSerialiseur
