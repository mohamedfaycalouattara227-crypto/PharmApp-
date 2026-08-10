"""
api/permissions.py
Classes de permission DRF basées sur la hiérarchie des 7 rôles PharmApp.
Chaque classe vérifie : authentifié + compte actif + non verrouillé + niveau de rôle.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

HIERARCHIE_ROLES = {
    "stagiaire":          0,
    "caissier":           1,
    "assistant":          2,
    "gestionnaire_stock": 3,
    "pharmacien_adjoint": 4,
    "titulaire":          5,
    "administrateur":     6,
}


def _niveau(role: str) -> int:
    return HIERARCHIE_ROLES.get(role, -1)


def _utilisateur_valide(request) -> bool:
    """Vérifie que l'utilisateur est authentifié, actif et non verrouillé."""
    user = getattr(request, "user", None)
    if user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "est_actif", getattr(user, "is_active", False)):
        return False
    if getattr(user, "est_verrouille", False):
        return False
    return True


class EstAuthentifie(BasePermission):
    """Tout utilisateur authentifié, actif et non verrouillé."""
    message = "Authentification requise ou compte inactif."

    def has_permission(self, request, view):
        return _utilisateur_valide(request)


class EstCaissierOuPlus(BasePermission):
    """Niveau minimum : Caissier (niveau 1)."""
    message = "Niveau Caissier minimum requis."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 1


class EstAssistantOuPlus(BasePermission):
    """Niveau minimum : Pharmacien assistant (niveau 2)."""
    message = "Niveau Pharmacien assistant minimum requis."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 2


class EstGestionnaireStockOuPlus(BasePermission):
    """Niveau minimum : Gestionnaire de stock (niveau 3)."""
    message = "Niveau Gestionnaire de stock minimum requis."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 3


class EstPharmacienAdjointOuPlus(BasePermission):
    """Niveau minimum : Pharmacien adjoint (niveau 4)."""
    message = "Niveau Pharmacien adjoint minimum requis."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 4


class EstPharmacienDiplome(BasePermission):
    """Pharmacien diplômé (adjoint ou titulaire) — accès ordonnances et produits contrôlés."""
    message = "Réservé aux pharmaciens diplômés."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return getattr(request.user, "est_pharmacien", False)


class EstTitulaire(BasePermission):
    """Niveau minimum : Titulaire ou Administrateur (niveau 5+)."""
    message = "Réservé au pharmacien titulaire ou à l'administrateur."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 5


class EstAdministrateur(BasePermission):
    """Niveau maximum : Administrateur système uniquement (niveau 6)."""
    message = "Réservé à l'administrateur système."

    def has_permission(self, request, view):
        if not _utilisateur_valide(request):
            return False
        return _niveau(getattr(request.user, "role", "")) >= 6


class LectureSeule(BasePermission):
    """Autorise uniquement les méthodes GET, HEAD et OPTIONS."""
    message = "Opération en lecture seule — modification non autorisée."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


# ─── Alias courts (compatibilité imports dans les vues) ───────────────────────
EstGestionnaireStock = EstGestionnaireStockOuPlus
EstCaissier = EstCaissierOuPlus
EstPharmacienAdjoint = EstPharmacienAdjointOuPlus
EstAssistant = EstAssistantOuPlus


class EstProprietaireOuTitulaire(BasePermission):
    """Autorise l'utilisateur propriétaire de la ressource ou le titulaire+."""
    message = "Accès réservé au propriétaire ou au titulaire."

    def has_object_permission(self, request, view, obj):
        if not _utilisateur_valide(request):
            return False
        if _niveau(getattr(request.user, "role", "")) >= 5:
            return True
        utilisateur_obj = getattr(obj, "utilisateur", getattr(obj, "vendeur", None))
        return utilisateur_obj == request.user
