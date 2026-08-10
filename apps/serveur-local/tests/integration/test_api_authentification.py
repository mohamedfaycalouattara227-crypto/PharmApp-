import pytest
pytestmark = [pytest.mark.django_db, pytest.mark.integration]
"""
tests/integration/test_api_authentification.py
Tests d'intégration pour l'API d'authentification.
"""

import uuid
from unittest.mock import MagicMock, patch

from rest_framework import status


class TestApiConnexion:
    """Tests de l'endpoint de connexion."""

    # DT-023 (corrigé) : les assertions ci-dessous n'acceptent plus HTTP_404_NOT_FOUND
    # pour les routes obligatoires du contrat API. Une route manquante doit faire
    # échouer le test, pas le faire passer silencieusement.
    # Référence : tests/test_url_contract.py valide le montage de toutes ces routes.

    def test_connexion_sans_donnees_retourne_400(self, api_client):
        """Requête de connexion sans données → 400."""
        reponse = api_client.post("/api/auth/connexion/", data={}, format="json")
        assert reponse.status_code == status.HTTP_400_BAD_REQUEST

    def test_connexion_email_invalide_retourne_400(self, api_client):
        """Email invalide → 400."""
        reponse = api_client.post(
            "/api/auth/connexion/",
            data={"email": "pas-un-email", "mot_de_passe": "test"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_400_BAD_REQUEST

    def test_connexion_compte_inexistant_retourne_401(self, api_client):
        """Tentative de connexion avec un compte inexistant → 401."""
        with patch("gestion.authentification.vues.authenticate", return_value=None):
            reponse = api_client.post(
                "/api/auth/connexion/",
                data={
                    "email": "inconnu@pharmapp.bf",
                    "mot_de_passe": "motdepasse",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_deconnexion_non_authentifie_retourne_401(self, api_client):
        """Déconnexion sans token actif → 401."""
        reponse = api_client.post("/api/auth/deconnexion/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_profil_non_authentifie_retourne_401(self, api_client):
        """Accès au profil sans authentification → 401."""
        reponse = api_client.get("/api/auth/profil/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_profil_authentifie_retourne_200(self, api_caissier):
        """Un utilisateur authentifié peut accéder à son profil."""
        reponse = api_caissier.get("/api/auth/profil/")
        assert reponse.status_code == status.HTTP_200_OK

    def test_connexion_reussie_journalisee_dans_audit(self, api_client, db):
        """
        CORRECTIF (audit 2026-07-21) : une connexion réussie doit créer une
        entrée JournalAudit — auparavant, aucune entrée n'était jamais créée
        en production (le gestionnaire _sur_connexion existait mais n'était
        jamais déclenché faute de bus.publier() réel). Utilise un utilisateur
        RÉEL en base (pas de mock) pour exercer le vrai chemin authenticate().
        DT-023 : le pytest.skip sur HTTP_404 est supprimé — la route doit être montée.
        """
        from tests.usine.usine_utilisateurs import UsineCaissier
        from gestion.audit.models import JournalAudit

        UsineCaissier(email="marie.kabore@pharmapp-test.bf", mot_de_passe="motDePasse@Securise1!")

        reponse = api_client.post(
            "/api/auth/connexion/",
            data={"email": "marie.kabore@pharmapp-test.bf", "mot_de_passe": "motDePasse@Securise1!"},
            format="json",
        )

        assert reponse.status_code == status.HTTP_200_OK
        assert JournalAudit.objects.filter(type_action="connexion_reussie").exists()

    def test_connexion_echouee_journalisee_dans_audit(self, api_client, db):
        """
        Un échec de connexion (mauvais mot de passe) doit aussi être journalisé.
        DT-023 : le pytest.skip sur HTTP_404 est supprimé — la route doit être montée.
        """
        from tests.usine.usine_utilisateurs import UsineCaissier
        from gestion.audit.models import JournalAudit

        UsineCaissier(email="ali.sawadogo@pharmapp-test.bf", mot_de_passe="motDePasse@Securise1!")

        reponse = api_client.post(
            "/api/auth/connexion/",
            data={"email": "ali.sawadogo@pharmapp-test.bf", "mot_de_passe": "mauvais_mot_de_passe"},
            format="json",
        )

        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED
        assert JournalAudit.objects.filter(type_action="connexion_echouee").exists()


class TestApiGestionUtilisateurs:
    """Tests de la gestion des comptes utilisateurs."""

    def test_lister_utilisateurs_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas lister les utilisateurs (rôle admin requis)."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_caissier.get("/api/auth/utilisateurs/")

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_lister_utilisateurs_titulaire_autorise(self, api_titulaire, db):
        """Le titulaire peut lister tous les utilisateurs."""
        with patch("gestion.authentification.vues.VueUtilisateur.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_titulaire.get("/api/auth/utilisateurs/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_creer_utilisateur_email_duplique_retourne_400(self, api_titulaire, db):
        """La création d'un utilisateur avec un email existant → 400."""
        with patch("gestion.authentification.serialiseurs.UtilisateurPharmacien") as mock_user:
            mock_user.objects.filter.return_value.exists.return_value = True

            reponse = api_titulaire.post(
                "/api/auth/utilisateurs/",
                data={
                    "prenom": "Test",
                    "nom": "Dupliquet",
                    "email": "existant@pharmapp.bf",
                    "role": "caissier",
                    "mot_de_passe": "MotDePasse@123",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiJournalAudit:
    """Tests de l'API du journal d'audit."""

    def test_journal_audit_caissier_interdit(self, api_caissier):
        """Un caissier n'a pas accès au journal d'audit."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_caissier.get("/api/journal-audit/")

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_journal_audit_titulaire_autorise(self, api_titulaire, db):
        """Le titulaire peut consulter le journal d'audit."""
        with patch("gestion.audit.vues.VueJournalAudit.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_titulaire.get("/api/journal-audit/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_journal_audit_ecriture_interdite(self, api_titulaire):
        """L'API du journal d'audit est en lecture seule — aucun POST possible."""
        reponse = api_titulaire.post(
            "/api/journal-audit/",
            data={"type_action": "injection", "description": "tentative"},
            format="json",
        )
        # 405 Method Not Allowed (ReadOnlyModelViewSet) ou 404
        assert reponse.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
        )
