"""
tests/unitaires/test_service_client.py
Tests unitaires du ServiceClient (gestion/clients/services.py).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unitaire


class TestServiceClient:
    """Tests du service métier pour les clients."""

    @pytest.fixture
    def service(self):
        from gestion.clients.services import ServiceClient
        return ServiceClient()

    def test_creer_client_requiert_caissier_minimum(self, service, stagiaire):
        from gestion.exceptions import PermissionRefusee
        stagiaire.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.creer_client(
                prenom="Test", nom="Client",
                donnees={"telephone": "+226 70 00 00 01"},
                utilisateur=stagiaire,
            )

    def test_modifier_client_inexistant_leve_erreur(self, service, caissier, db):
        with patch("gestion.clients.services.Client") as mock_client:
            mock_client.objects.filter.return_value.first.return_value = None
            with pytest.raises((ValueError, Exception)):
                service.modifier_client(
                    client_id=uuid.uuid4(),
                    donnees={"prenom": "Nouveau"},
                    utilisateur=caissier,
                )

    def test_credit_non_autorise_leve_erreur(self, service, client_mock):
        from gestion.exceptions import CreditNonAutorise
        with pytest.raises(CreditNonAutorise):
            service.verifier_credit_disponible(
                client=client_mock,  # credit_autorise=False
                montant_commande=Decimal("1000.00"),
            )

    def test_plafond_credit_depasse_leve_erreur(self, service, client_credit_mock):
        from gestion.exceptions import PlafondCreditDepasse
        with patch.object(
            service, "_calculer_solde_credit",
            return_value={
                "plafond": Decimal("50000.00"),
                "utilise": Decimal("48000.00"),
                "disponible": Decimal("2000.00"),
            }
        ):
            with pytest.raises(PlafondCreditDepasse):
                service.verifier_credit_disponible(
                    client=client_credit_mock,
                    montant_commande=Decimal("5000.00"),  # > 2000 disponible
                )

    def test_credit_disponible_passe_sans_erreur(self, service, client_credit_mock):
        """Si le solde disponible est suffisant, aucune exception n'est levée."""
        with patch.object(
            service, "_calculer_solde_credit",
            return_value={
                "plafond": Decimal("50000.00"),
                "utilise": Decimal("10000.00"),
                "disponible": Decimal("40000.00"),
            }
        ):
            # Ne doit pas lever d'exception
            service.verifier_credit_disponible(
                client=client_credit_mock,
                montant_commande=Decimal("5000.00"),
            )

    def test_anonymiser_client_requiert_pharmacien_adjoint(self, service, caissier, db):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.anonymiser_client(
                client_id=uuid.uuid4(),
                utilisateur=caissier,
            )

    def test_anonymiser_client_inexistant_leve_erreur(self, service, pharmacien_adjoint, db):
        with patch("gestion.clients.services.Client") as mock_client:
            mock_client.objects.filter.return_value.select_for_update.return_value.first.return_value = None
            with pytest.raises((ValueError, Exception)):
                service.anonymiser_client(
                    client_id=uuid.uuid4(),
                    utilisateur=pharmacien_adjoint,
                )

