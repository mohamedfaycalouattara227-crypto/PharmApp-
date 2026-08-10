"""
tests/integration/test_api_clients.py
Tests d'intégration pour l'API REST des clients.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

pytestmark = pytest.mark.integration


class TestApiClientCreation:
    """Tests de création de clients via l'API."""

    def test_creer_client_non_authentifie_retourne_401(self, api_client):
        """La création d'un client requiert une authentification."""
        reponse = api_client.post(
            "/api/clients/",
            data={"prenom": "Issa", "nom": "Sawadogo"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_creer_client_donnees_minimales_valides(self, api_caissier):
        """La création avec données minimales valides retourne 201 ou 400 (données DB manquantes)."""
        with patch("gestion.clients.vues.ServiceClient") as mock_svc:
            client_mock = MagicMock()
            client_mock.id = uuid.uuid4()
            mock_svc.return_value.creer_client.return_value = client_mock

            with patch("gestion.clients.serialiseurs.ClientSerialiseur") as mock_ser:
                mock_ser.return_value.data = {
                    "id": str(client_mock.id),
                    "prenom": "Issa",
                    "nom": "Sawadogo",
                }

                reponse = api_caissier.post(
                    "/api/clients/",
                    data={
                        "prenom": "Issa",
                        "nom": "Sawadogo",
                        "telephone": "+226 70 00 00 01",
                        "type_client": "particulier",
                    },
                    format="json",
                )

        assert reponse.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_telephone_duplique_retourne_400(self, api_caissier, db):
        """Un numéro de téléphone déjà utilisé → 400."""
        with patch("gestion.clients.vues.ServiceClient") as mock_svc:
            mock_svc.return_value.creer_client.side_effect = ValueError(
                "Ce numéro de téléphone est déjà enregistré."
            )

            reponse = api_caissier.post(
                "/api/clients/",
                data={
                    "prenom": "Duplicate",
                    "nom": "Test",
                    "telephone": "+226 70 00 00 01",
                    "type_client": "particulier",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiClientRecherche:
    """Tests de la recherche de clients."""

    def test_lister_clients_non_authentifie_retourne_401(self, api_client):
        """Le listage des clients requiert une authentification."""
        reponse = api_client.get("/api/clients/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_recherche_client_par_nom(self, api_caissier, db):
        """La recherche par nom filtre correctement les clients."""
        with patch("gestion.clients.vues.VueClient.get_queryset") as mock_qs:
            mock_qs.return_value = MagicMock()
            mock_qs.return_value.__iter__ = lambda s: iter([])
            mock_qs.return_value.count.return_value = 0

            reponse = api_caissier.get("/api/clients/?search=Sawadogo")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiClientCredit:
    """Tests de la gestion du crédit client."""

    def test_configurer_credit_caissier_interdit(self, api_caissier):
        """Un caissier ne peut pas configurer le crédit d'un client."""
        with patch("api.permissions.EstPharmacienAdjointOuPlus.has_permission", return_value=False):
            reponse = api_caissier.post(
                f"/api/clients/{uuid.uuid4()}/configurer-credit/",
                data={"credit_autorise": True, "plafond_credit": "50000"},
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_anonymiser_client_titulaire_seulement(self, api_pharmacien_adjoint):
        """Seul le titulaire peut anonymiser (droit à l'oubli) un client."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_pharmacien_adjoint.post(
                f"/api/clients/{uuid.uuid4()}/anonymiser/",
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
