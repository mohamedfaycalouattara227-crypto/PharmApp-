"""
tests/integration/test_repositories_integration.py
Tests d'intégration des repositories avec une vraie base de données SQLite.
"""

import datetime
import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration


class TestDepotVenteIntegration:
    """Tests d'intégration du DepotVente avec SQLite en mémoire."""

    @pytest.fixture(autouse=True)
    def vider_donnees(self, db):
        """Nettoie les données entre les tests."""
        pass

    def test_trouver_par_id_retourne_none_pour_id_inexistant(self, db):
        """trouver_par_id() retourne None pour un UUID qui n'existe pas."""
        from infrastructure.repositories.ventes import DepotVente
        depot = DepotVente()
        assert depot.trouver_par_id(uuid.uuid4()) is None

    def test_total_journalier_sans_vente_retourne_zero(self, db):
        """total_journalier() retourne 0.00 si aucune vente pour la date."""
        from infrastructure.repositories.ventes import DepotVente
        depot = DepotVente()
        total = depot.total_journalier(datetime.date(2020, 1, 1))
        assert total == Decimal("0.00")

    def test_compter_par_mode_paiement_vide(self, db):
        """compter_par_mode_paiement() retourne un dict vide s'il n'y a pas de ventes."""
        from infrastructure.repositories.ventes import DepotVente
        depot = DepotVente()
        result = depot.compter_par_mode_paiement(datetime.date(2020, 1, 1))
        assert result == {}

    def test_nombre_ventes_journalier_zero(self, db):
        """nombre_ventes_journalier() retourne 0 si aucune vente."""
        from infrastructure.repositories.ventes import DepotVente
        depot = DepotVente()
        count = depot.nombre_ventes_journalier(datetime.date(2020, 1, 1))
        assert count == 0


class TestDepotClientIntegration:
    """Tests d'intégration du DepotClient."""

    def test_trouver_par_telephone_inexistant(self, db):
        """trouver_par_telephone() retourne None si le numéro n'existe pas."""
        from infrastructure.repositories.clients import DepotClient
        depot = DepotClient()
        assert depot.trouver_par_telephone("+226 99 99 99 99") is None

    def test_trouver_par_numero_assurance_inexistant(self, db):
        """trouver_par_numero_assurance() retourne None si le numéro n'existe pas."""
        from infrastructure.repositories.clients import DepotClient
        depot = DepotClient()
        assert depot.trouver_par_numero_assurance("ASS-INEXISTANT") is None

    def test_lister_clients_vide(self, db):
        """lister() retourne une liste vide si aucun client en DB."""
        from infrastructure.repositories.clients import DepotClient
        depot = DepotClient()
        assert depot.lister() == []

    def test_historique_achats_client_inexistant(self, db):
        """historique_achats() retourne une liste vide pour un client inexistant."""
        from infrastructure.repositories.clients import DepotClient
        depot = DepotClient()
        assert depot.historique_achats(uuid.uuid4()) == []


class TestDepotLotIntegration:
    """Tests d'intégration du DepotLot."""

    def test_lots_perimant_bientot_vide(self, db):
        """lots_perimant_bientot() retourne une liste vide si aucun lot proche expiration."""
        from infrastructure.repositories.catalogue import DepotLot
        depot = DepotLot()
        lots = depot.lots_perimant_bientot(jours=90)
        assert lots == []

    def test_trouver_par_id_lot_inexistant(self, db):
        """trouver_par_id() retourne None pour un lot qui n'existe pas."""
        from infrastructure.repositories.catalogue import DepotLot
        depot = DepotLot()
        assert depot.trouver_par_id(uuid.uuid4()) is None

    def test_lister_lots_filtres(self, db):
        """lister() sans données retourne une liste vide."""
        from infrastructure.repositories.catalogue import DepotLot
        depot = DepotLot()
        lots = depot.lister()
        assert lots == []


class TestDepotMedicamentIntegration:
    """Tests d'intégration du DepotMedicament."""

    def test_trouver_par_code_cis_inexistant(self, db):
        """trouver_par_code_cis() retourne None si le code n'existe pas."""
        from infrastructure.repositories.catalogue import DepotMedicament
        depot = DepotMedicament()
        assert depot.trouver_par_code_cis("CIS-INEXISTANT") is None

    def test_medicaments_en_alerte_vide(self, db):
        """medicaments_en_alerte() retourne une liste vide sans données."""
        from infrastructure.repositories.catalogue import DepotMedicament
        depot = DepotMedicament()
        assert depot.medicaments_en_alerte() == []


class TestDepotJournalAuditIntegration:
    """Tests d'intégration du DepotJournalAudit."""

    def test_lister_journal_vide(self, db):
        """lister() retourne une liste vide si le journal est vide."""
        from infrastructure.repositories.audit import DepotJournalAudit
        depot = DepotJournalAudit()
        assert depot.lister() == []

    def test_verifier_integrite_journal_vide(self, db):
        """verifier_integrite() retourne 0 total si le journal est vide."""
        from infrastructure.repositories.audit import DepotJournalAudit
        depot = DepotJournalAudit()
        resultat = depot.verifier_integrite()
        assert resultat["total"] == 0
        assert resultat["corrompues"] == []
        assert resultat["integrite_ok"] is True
