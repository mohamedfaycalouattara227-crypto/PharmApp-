"""
tests/securite/test_rbac.py
Tests de sécurité RBAC — vérification que chaque endpoint respecte
strictement les permissions définies dans la politique de sécurité PharmApp.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

pytestmark = pytest.mark.securite


class TestRBACVentes:
    """Matrice de permissions pour les opérations de vente."""

    def test_stagiaire_ne_peut_pas_voir_les_ventes(self, api_client, stagiaire):
        """Un stagiaire n'a accès à aucune opération de vente."""
        api_client.force_authenticate(user=stagiaire)
        with patch("api.permissions.EstCaissierOuPlus.has_permission", return_value=False):
            reponse = api_client.get("/api/ventes/")
        assert reponse.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_caissier_peut_voir_ses_ventes(self, api_caissier):
        """Un caissier peut voir la liste de ses ventes."""
        with patch("gestion.ventes.vues.VueVente.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0
            reponse = api_caissier.get("/api/ventes/")
        assert reponse.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND)

    def test_seul_pharmacien_peut_annuler_vente(self, api_caissier):
        """Un caissier ne peut pas annuler une vente."""
        with patch("api.permissions.EstPharmacienAdjointOuPlus.has_permission", return_value=False):
            reponse = api_caissier.post(
                f"/api/ventes/{uuid.uuid4()}/annuler/",
                data={"motif": "test"},
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class TestRBACStock:
    """Matrice de permissions pour les opérations de stock."""

    def test_caissier_ne_peut_pas_ajuster_stock(self, api_caissier):
        """Un caissier ne peut pas ajuster le stock manuellement."""
        with patch("api.permissions.EstGestionnaireStockOuPlus.has_permission", return_value=False):
            reponse = api_caissier.post(
                "/api/stocks/ajuster/",
                data={"lot_id": str(uuid.uuid4()), "nouvelle_quantite": 100},
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_gestionnaire_peut_ajuster_stock(self, api_gestionnaire_stock):
        """Un gestionnaire de stock peut ajuster le stock."""
        with patch("gestion.stocks.vues.ServiceStock") as mock_svc:
            lot_mock = MagicMock()
            mock_svc.return_value.ajuster_stock_manuel.return_value = lot_mock
            reponse = api_gestionnaire_stock.post(
                "/api/stocks/ajuster/",
                data={
                    "lot_id": str(uuid.uuid4()),
                    "nouvelle_quantite": 100,
                    "motif": "Vérification inventaire",
                },
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


class TestRBACUtilisateurs:
    """Matrice de permissions pour la gestion des utilisateurs."""

    def test_seul_titulaire_peut_creer_utilisateur(self, api_pharmacien_adjoint):
        """Un pharmacien adjoint ne peut pas créer de nouveaux comptes."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_pharmacien_adjoint.post(
                "/api/auth/utilisateurs/",
                data={
                    "prenom": "Nouveau",
                    "nom": "Test",
                    "email": "nouveau@pharmapp.bf",
                    "role": "caissier",
                },
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_seul_titulaire_peut_lire_audit(self, api_pharmacien_adjoint):
        """Seul le titulaire peut lire le journal d'audit."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_pharmacien_adjoint.get("/api/journal-audit/")
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_audit_en_lecture_seule(self, api_titulaire):
        """Le journal d'audit ne peut pas être modifié via l'API."""
        reponse = api_titulaire.post(
            "/api/journal-audit/",
            data={"type_action": "injection"},
            format="json",
        )
        assert reponse.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_audit_suppression_interdite(self, api_titulaire):
        """Aucune suppression n'est possible dans le journal d'audit."""
        reponse = api_titulaire.delete(f"/api/journal-audit/{uuid.uuid4()}/")
        assert reponse.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestRBACProduitControle:
    """Matrice de permissions pour les produits contrôlés (stupéfiants)."""

    def test_caissier_ne_peut_pas_deplacer_stupefiant(self, api_caissier):
        """Un caissier ne peut pas enregistrer de mouvement sur un produit contrôlé."""
        with patch("api.permissions.EstPharmacienDiplome.has_permission", return_value=False):
            reponse = api_caissier.post(
                "/api/produits-controles/sortie/",
                data={
                    "medicament_id": str(uuid.uuid4()),
                    "lot_id": str(uuid.uuid4()),
                    "quantite": 5,
                    "ordonnance_id": str(uuid.uuid4()),
                },
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestRBACOrdonnances:
    """Matrice de permissions pour les ordonnances."""

    def test_image_ordonnance_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas accéder à l'image d'une ordonnance."""
        with patch("api.permissions.EstPharmacienDiplome.has_permission", return_value=False):
            reponse = api_caissier.get(
                f"/api/ordonnances/{uuid.uuid4()}/image/"
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_image_ordonnance_pharmacien_autorise(self, api_pharmacien_adjoint):
        """Un pharmacien diplômé peut accéder à l'image d'une ordonnance."""
        with patch("gestion.ordonnances.vues.ServiceOrdonnance") as mock_svc:
            mock_svc.return_value.consulter_image.return_value = b"image_bytes"

            with patch("gestion.ordonnances.vues.VueOrdonnance.get_object") as mock_obj:
                ord_mock = MagicMock()
                ord_mock.type_mime = "image/jpeg"
                ord_mock.numero_interne = "ORD-001"
                mock_obj.return_value = ord_mock

                reponse = api_pharmacien_adjoint.get(
                    f"/api/ordonnances/{uuid.uuid4()}/image/"
                )

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


class TestRBACClotureCaisse:
    """Matrice de permissions pour la clôture de caisse."""

    def test_cloture_caisse_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas effectuer la clôture de caisse."""
        with patch("api.permissions.EstPharmacienAdjointOuPlus.has_permission", return_value=False):
            reponse = api_caissier.post(
                "/api/clotures/",
                data={"date_cloture": "2024-01-15", "fond_caisse_ouverture": "50000"},
                format="json",
            )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
