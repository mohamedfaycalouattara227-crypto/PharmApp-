"""
apps/identite/permissions.py
Classes de permissions pour les endpoints cloud.
"""

from rest_framework.permissions import BasePermission


class EstAdminCloud(BasePermission):
    """
    Autorise uniquement les requêtes authentifiées via le token admin cloud
    (AuthenticationParTokenAdmin). Les officines (clé API) n'ont pas accès.
    """
    message = "Accès réservé à l'administrateur PharmApp Cloud."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.auth == "admin"
        )


class EstOfficineActive(BasePermission):
    """
    Autorise uniquement les requêtes authentifiées via une clé API d'officine
    active avec un abonnement valide.
    """
    message = "Officine inactive ou abonnement expiré."

    def has_permission(self, request, view) -> bool:
        officine = getattr(request, "user", None)
        if not officine:
            return False
        # request.user est une instance Officine si authentifiée par clé API
        from apps.identite.models import Officine
        if not isinstance(officine, Officine):
            return False
        return officine.abonnement_actif
