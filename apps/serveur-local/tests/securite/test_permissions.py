"""
tests/securite/test_permissions.py
Tests de sécurité pour le contrôle d'accès basé sur les rôles (RBAC).
Couverture : api/permissions.py + hiérarchie des rôles PharmApp.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from api.permissions import (
    EstAuthentifie,
    EstCaissierOuPlus,
    EstAssistantOuPlus,
    EstGestionnaireStockOuPlus,
    EstPharmacienAdjointOuPlus,
    EstPharmacienDiplome,
    EstTitulaire,
    LectureSeule,
    HIERARCHIE_ROLES,
)

pytestmark = pytest.mark.securite


def _creer_requete(role: str, est_actif: bool = True, est_verrouille: bool = False):
    """Crée une requête mock avec un utilisateur du rôle indiqué."""
    requete = MagicMock()
    requete.user.is_authenticated = True
    requete.user.est_actif = est_actif
    requete.user.est_verrouille = est_verrouille
    requete.user.role = role
    requete.user.est_pharmacien = role in ("pharmacien_adjoint", "titulaire")
    return requete


# ─── Tests EstAuthentifie ──────────────────────────────────────────────────────

class TestEstAuthentifie:
    """Tests de la permission EstAuthentifie."""

    def test_utilisateur_authentifie_actif_autorise(self):
        """Un utilisateur authentifié et actif est autorisé."""
        perm = EstAuthentifie()
        requete = _creer_requete("caissier")
        assert perm.has_permission(requete, None) is True

    def test_utilisateur_non_authentifie_refuse(self):
        """Un utilisateur non authentifié est refusé."""
        perm = EstAuthentifie()
        requete = MagicMock()
        requete.user.is_authenticated = False
        assert perm.has_permission(requete, None) is False

    def test_utilisateur_desactive_refuse(self):
        """Un compte désactivé est refusé."""
        perm = EstAuthentifie()
        requete = _creer_requete("caissier", est_actif=False)
        assert perm.has_permission(requete, None) is False

    def test_utilisateur_verrouille_refuse(self):
        """Un compte verrouillé est refusé."""
        perm = EstAuthentifie()
        requete = _creer_requete("caissier", est_verrouille=True)
        assert perm.has_permission(requete, None) is False

    def test_utilisateur_aucun_refuse(self):
        """request.user = None est refusé."""
        perm = EstAuthentifie()
        requete = MagicMock()
        requete.user = None
        assert perm.has_permission(requete, None) is False


# ─── Tests EstCaissierOuPlus ──────────────────────────────────────────────────

class TestEstCaissierOuPlus:
    """Tests de la hiérarchie de permission Caissier+."""

    @pytest.fixture
    def perm(self):
        return EstCaissierOuPlus()

    def test_stagiaire_refuse(self, perm):
        assert perm.has_permission(_creer_requete("stagiaire"), None) is False

    def test_caissier_autorise(self, perm):
        assert perm.has_permission(_creer_requete("caissier"), None) is True

    def test_assistant_autorise(self, perm):
        assert perm.has_permission(_creer_requete("assistant"), None) is True

    def test_gestionnaire_stock_autorise(self, perm):
        assert perm.has_permission(_creer_requete("gestionnaire_stock"), None) is True

    def test_pharmacien_adjoint_autorise(self, perm):
        assert perm.has_permission(_creer_requete("pharmacien_adjoint"), None) is True

    def test_titulaire_autorise(self, perm):
        assert perm.has_permission(_creer_requete("titulaire"), None) is True

    def test_administrateur_autorise(self, perm):
        assert perm.has_permission(_creer_requete("administrateur"), None) is True

    def test_role_inconnu_refuse(self, perm):
        """Un rôle non reconnu est refusé (niveau = -1 < 1)."""
        assert perm.has_permission(_creer_requete("role_inexistant"), None) is False


# ─── Tests EstGestionnaireStockOuPlus ─────────────────────────────────────────

class TestEstGestionnaireStockOuPlus:
    """Tests de la permission Gestionnaire de stock+."""

    @pytest.fixture
    def perm(self):
        return EstGestionnaireStockOuPlus()

    def test_caissier_refuse(self, perm):
        assert perm.has_permission(_creer_requete("caissier"), None) is False

    def test_assistant_refuse(self, perm):
        assert perm.has_permission(_creer_requete("assistant"), None) is False

    def test_gestionnaire_stock_autorise(self, perm):
        assert perm.has_permission(_creer_requete("gestionnaire_stock"), None) is True

    def test_pharmacien_adjoint_autorise(self, perm):
        assert perm.has_permission(_creer_requete("pharmacien_adjoint"), None) is True

    def test_titulaire_autorise(self, perm):
        assert perm.has_permission(_creer_requete("titulaire"), None) is True


# ─── Tests EstPharmacienAdjointOuPlus ─────────────────────────────────────────

class TestEstPharmacienAdjointOuPlus:
    """Tests de la permission Pharmacien adjoint+."""

    @pytest.fixture
    def perm(self):
        return EstPharmacienAdjointOuPlus()

    def test_gestionnaire_stock_refuse(self, perm):
        assert perm.has_permission(_creer_requete("gestionnaire_stock"), None) is False

    def test_pharmacien_adjoint_autorise(self, perm):
        assert perm.has_permission(_creer_requete("pharmacien_adjoint"), None) is True

    def test_titulaire_autorise(self, perm):
        assert perm.has_permission(_creer_requete("titulaire"), None) is True

    def test_caissier_refuse(self, perm):
        assert perm.has_permission(_creer_requete("caissier"), None) is False


# ─── Tests EstPharmacienDiplome ────────────────────────────────────────────────

class TestEstPharmacienDiplome:
    """Tests de la permission Pharmacien diplômé."""

    @pytest.fixture
    def perm(self):
        return EstPharmacienDiplome()

    def test_caissier_refuse(self, perm):
        requete = _creer_requete("caissier")
        requete.user.est_pharmacien = False
        assert perm.has_permission(requete, None) is False

    def test_gestionnaire_stock_refuse(self, perm):
        requete = _creer_requete("gestionnaire_stock")
        requete.user.est_pharmacien = False
        assert perm.has_permission(requete, None) is False

    def test_pharmacien_adjoint_autorise(self, perm):
        requete = _creer_requete("pharmacien_adjoint")
        requete.user.est_pharmacien = True
        assert perm.has_permission(requete, None) is True

    def test_titulaire_autorise(self, perm):
        requete = _creer_requete("titulaire")
        requete.user.est_pharmacien = True
        assert perm.has_permission(requete, None) is True


# ─── Tests EstTitulaire ────────────────────────────────────────────────────────

class TestEstTitulaire:
    """Tests de la permission Titulaire (accès le plus restrictif)."""

    @pytest.fixture
    def perm(self):
        return EstTitulaire()

    def test_pharmacien_adjoint_refuse(self, perm):
        assert perm.has_permission(_creer_requete("pharmacien_adjoint"), None) is False

    def test_titulaire_autorise(self, perm):
        assert perm.has_permission(_creer_requete("titulaire"), None) is True

    def test_administrateur_autorise(self, perm):
        assert perm.has_permission(_creer_requete("administrateur"), None) is True

    def test_tout_autre_role_refuse(self, perm):
        for role in ("stagiaire", "caissier", "assistant", "gestionnaire_stock"):
            assert perm.has_permission(_creer_requete(role), None) is False, \
                f"Le rôle '{role}' ne doit pas avoir accès à EstTitulaire"


# ─── Tests LectureSeule ────────────────────────────────────────────────────────

class TestLectureSeule:
    """Tests de la permission LectureSeule."""

    @pytest.fixture
    def perm(self):
        return LectureSeule()

    def test_get_autorise(self, perm):
        requete = MagicMock()
        requete.method = "GET"
        assert perm.has_permission(requete, None) is True

    def test_head_autorise(self, perm):
        requete = MagicMock()
        requete.method = "HEAD"
        assert perm.has_permission(requete, None) is True

    def test_options_autorise(self, perm):
        requete = MagicMock()
        requete.method = "OPTIONS"
        assert perm.has_permission(requete, None) is True

    def test_post_refuse(self, perm):
        requete = MagicMock()
        requete.method = "POST"
        assert perm.has_permission(requete, None) is False

    def test_put_refuse(self, perm):
        requete = MagicMock()
        requete.method = "PUT"
        assert perm.has_permission(requete, None) is False

    def test_patch_refuse(self, perm):
        requete = MagicMock()
        requete.method = "PATCH"
        assert perm.has_permission(requete, None) is False

    def test_delete_refuse(self, perm):
        requete = MagicMock()
        requete.method = "DELETE"
        assert perm.has_permission(requete, None) is False


# ─── Tests de la hiérarchie globale ──────────────────────────────────────────

class TestHierarchieRoles:
    """Tests de cohérence de la hiérarchie des rôles."""

    def test_tous_les_roles_sont_definis(self):
        """Tous les rôles standard sont dans la hiérarchie."""
        roles_attendus = {
            "stagiaire", "caissier", "assistant", "gestionnaire_stock",
            "pharmacien_adjoint", "titulaire", "administrateur",
        }
        assert roles_attendus.issubset(set(HIERARCHIE_ROLES.keys()))

    def test_niveaux_strictement_croissants(self):
        """Les niveaux augmentent strictement du rôle le plus faible au plus fort."""
        roles_ordonnes = [
            "stagiaire", "caissier", "assistant", "gestionnaire_stock",
            "pharmacien_adjoint", "titulaire", "administrateur",
        ]
        niveaux = [HIERARCHIE_ROLES[r] for r in roles_ordonnes]
        for i in range(1, len(niveaux)):
            assert niveaux[i] > niveaux[i - 1], (
                f"Niveau de '{roles_ordonnes[i]}' ({niveaux[i]}) devrait être "
                f"supérieur à '{roles_ordonnes[i-1]}' ({niveaux[i-1]})"
            )

    def test_stagiaire_est_le_plus_bas(self):
        """Le stagiaire a le niveau le plus bas."""
        niveau_stagiaire = HIERARCHIE_ROLES["stagiaire"]
        for role, niveau in HIERARCHIE_ROLES.items():
            if role != "stagiaire":
                assert niveau > niveau_stagiaire, \
                    f"'{role}' ({niveau}) devrait être au-dessus du stagiaire ({niveau_stagiaire})"

    def test_administrateur_est_le_plus_haut(self):
        """L'administrateur a le niveau le plus élevé."""
        niveau_admin = HIERARCHIE_ROLES["administrateur"]
        for role, niveau in HIERARCHIE_ROLES.items():
            if role != "administrateur":
                assert niveau <= niveau_admin, \
                    f"'{role}' ({niveau}) ne devrait pas dépasser l'administrateur ({niveau_admin})"
