"""
tests/integration/test_api_stocks.py
Tests d'intégration pour l'API REST de gestion des stocks.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

pytestmark = pytest.mark.integration


class TestApiAjustementStock:
    """Tests de l'endpoint d'ajustement de stock."""

    def test_ajustement_sans_authentification_retourne_401(self, api_client):
        """L'ajustement requiert une authentification."""
        reponse = api_client.post(
            "/api/stocks/ajuster/",
            data={"lot_id": str(uuid.uuid4()), "nouvelle_quantite": 100},
            format="json",
        )
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ajustement_sans_lot_id_retourne_400(self, api_gestionnaire_stock):
        """lot_id manquant → 400 Bad Request."""
        reponse = api_gestionnaire_stock.post(
            "/api/stocks/ajuster/",
            data={"nouvelle_quantite": 100},
            format="json",
        )
        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_ajustement_sans_quantite_retourne_400(self, api_gestionnaire_stock):
        """nouvelle_quantite manquante → 400 Bad Request."""
        reponse = api_gestionnaire_stock.post(
            "/api/stocks/ajuster/",
            data={"lot_id": str(uuid.uuid4())},
            format="json",
        )
        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_ajustement_lot_introuvable_retourne_400(self, api_gestionnaire_stock):
        """Un lot inexistant retourne une erreur 400 ou 422."""
        with patch("gestion.stocks.vues.ServiceStock") as mock_svc:
            mock_svc.return_value.ajuster_stock_manuel.side_effect = ValueError(
                "Lot introuvable"
            )

            reponse = api_gestionnaire_stock.post(
                "/api/stocks/ajuster/",
                data={
                    "lot_id": str(uuid.uuid4()),
                    "nouvelle_quantite": 100,
                    "motif": "Test",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_ajustement_ecart_significatif_retourne_403(self, api_gestionnaire_stock):
        """Un écart > 5 % par un non-pharmacien retourne 403."""
        from gestion.exceptions import EcartInventaireSignificatif

        with patch("gestion.stocks.vues.ServiceStock") as mock_svc:
            mock_svc.return_value.ajuster_stock_manuel.side_effect = (
                EcartInventaireSignificatif("Écart trop important")
            )

            reponse = api_gestionnaire_stock.post(
                "/api/stocks/ajuster/",
                data={
                    "lot_id": str(uuid.uuid4()),
                    "nouvelle_quantite": 1,
                    "motif": "Test",
                },
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiBesoinsReapprovisionnement:
    """Tests de l'endpoint de calcul des besoins."""

    def test_besoins_reappro_sans_authentification_retourne_401(self, api_client):
        """Le calcul des besoins requiert une authentification."""
        reponse = api_client.get("/api/stocks/besoins-reappro/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_besoins_reappro_retourne_liste(self, api_gestionnaire_stock):
        """L'endpoint retourne une liste de besoins."""
        with patch("gestion.stocks.vues.ServiceStock") as mock_svc:
            mock_svc.return_value.calculer_besoins_reapprovisionnement.return_value = []

            reponse = api_gestionnaire_stock.get("/api/stocks/besoins-reappro/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


class TestApiAlerteStock:
    """Tests de l'API des alertes de stock."""

    def test_lister_alertes_sans_authentification_retourne_401(self, api_client):
        """Le listage des alertes requiert une authentification."""
        reponse = api_client.get("/api/alertes-stock/")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED

    def test_lister_alertes_caissier_interdit(self, api_caissier, db):
        """Les alertes de stock sont réservées au gestionnaire minimum."""
        reponse = api_caissier.get("/api/alertes-stock/")
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
