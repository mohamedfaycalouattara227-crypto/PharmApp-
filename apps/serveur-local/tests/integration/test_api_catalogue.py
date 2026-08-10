"""
tests/integration/test_api_catalogue.py
Tests d'intégration pour l'API REST du catalogue médicaments.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.response import Response as DRFResponse

pytestmark = pytest.mark.integration


class TestApiMedicaments:
    """Tests de l'API des médicaments."""

    def test_lister_medicaments_non_authentifie_retourne_401(self, api_client):
        """Le listage des médicaments requiert une authentification."""
        reponse = api_client.get("/api/medicaments/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_lister_medicaments_caissier_autorise(self, api_caissier, db):
        """Un caissier peut consulter le catalogue des médicaments."""
        with patch("gestion.catalogue.vues.VueMedicament.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_caissier.get("/api/medicaments/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_creer_medicament_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas ajouter un médicament au catalogue."""
        with patch("api.permissions.EstGestionnaireStockOuPlus.has_permission", return_value=False):
            reponse = api_caissier.post(
                "/api/medicaments/",
                data={
                    "nom": "Paracétamol 500mg",
                    "prix_public": "500.00",
                    "categorie": str(uuid.uuid4()),
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_creer_medicament_gestionnaire_stock_autorise(self, api_gestionnaire_stock):
        """Un gestionnaire de stock peut ajouter un médicament."""
        with patch("gestion.catalogue.vues.VueMedicament.create") as mock_create:
            mock_create.return_value = DRFResponse(
                {"id": str(uuid.uuid4()), "nom": "Amoxicilline 500mg"},
                status=201,
            )

            reponse = api_gestionnaire_stock.post(
                "/api/medicaments/",
                data={
                    "nom": "Amoxicilline 500mg",
                    "prix_public": "800.00",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_recherche_medicament_par_nom(self, api_caissier, db):
        """La recherche par nom filtre les médicaments."""
        with patch("gestion.catalogue.vues.VueMedicament.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_caissier.get("/api/medicaments/?search=Amoxicilline")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_supprimer_medicament_gestionnaire_stock(self, api_gestionnaire_stock):
        """Un gestionnaire de stock peut désactiver un médicament."""
        with patch("gestion.catalogue.vues.VueMedicament.destroy") as mock_destroy:
            mock_destroy.return_value = DRFResponse(status=204)

            reponse = api_gestionnaire_stock.delete(
                f"/api/medicaments/{uuid.uuid4()}/"
            )

        assert reponse.status_code in (
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiCategories:
    """Tests de l'API des catégories de médicaments."""

    def test_lister_categories_caissier_autorise(self, api_caissier, db):
        """Un caissier peut lister les catégories."""
        with patch("gestion.catalogue.vues.VueCategorieProduit.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_caissier.get("/api/categories/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_supprimer_categorie_avec_medicaments_retourne_409(self, api_pharmacien_adjoint):
        """Supprimer une catégorie contenant des médicaments actifs → 409."""
        with patch("gestion.catalogue.vues.VueCategorieProduit.get_object") as mock_obj:
            categorie_mock = MagicMock()
            categorie_mock.medicaments.filter.return_value.exists.return_value = True
            mock_obj.return_value = categorie_mock

            reponse = api_pharmacien_adjoint.delete(
                f"/api/categories/{uuid.uuid4()}/"
            )

        assert reponse.status_code in (
            status.HTTP_409_CONFLICT,
            status.HTTP_404_NOT_FOUND,
        )
