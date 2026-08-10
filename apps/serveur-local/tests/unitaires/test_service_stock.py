"""
tests/unitaires/test_service_stock.py
Tests unitaires du ServiceStock.
Couverture cible : 100 % de gestion/stocks/services.py
"""

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from gestion.stocks.services import ServiceStock

pytestmark = pytest.mark.unitaire


# ─── Permissions ──────────────────────────────────────────────────────────────

class TestServiceStockPermissions:
    """Tests des contrôles de permissions dans ServiceStock."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_ajuster_stock_requiert_gestionnaire_stock(self, service, caissier):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.ajuster_stock_manuel(
                lot_id=uuid.uuid4(), nouvelle_quantite=100,
                motif="Test", utilisateur=caissier,
            )

    def test_receptionner_livraison_requiert_gestionnaire_stock(self, service, caissier):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(), lignes_reception=[],
                utilisateur=caissier,
            )

    def test_demarrer_inventaire_requiert_gestionnaire_stock(self, service, caissier):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.demarrer_inventaire(utilisateur=caissier)

    def test_ajuster_stock_lot_introuvable(self, service, gestionnaire_stock, db):
        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = None
            with pytest.raises(ValueError, match="Lot introuvable"):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(), nouvelle_quantite=100,
                    motif="Test", utilisateur=gestionnaire_stock,
                )

    def test_ajuster_stock_lot_inactif_leve_erreur(self, service, gestionnaire_stock, db):
        from gestion.exceptions import LotInactif
        lot_mock = MagicMock()
        lot_mock.est_actif = False
        lot_mock.numero_lot = "LOT-001"
        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = lot_mock
            with pytest.raises(LotInactif):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(), nouvelle_quantite=100,
                    motif="Test", utilisateur=gestionnaire_stock,
                )

    def test_ecart_important_requiert_pharmacien_adjoint(self, service, gestionnaire_stock, db):
        from gestion.exceptions import EcartInventaireSignificatif
        lot_mock = MagicMock()
        lot_mock.est_actif = True
        lot_mock.quantite_disponible = 100
        lot_mock.medicament.nom = "Amoxicilline"
        lot_mock.numero_lot = "LOT-001"
        # Gestionnaire seul, sans droit adjoint
        gestionnaire_stock.a_permission_role = lambda r: r == "gestionnaire_stock"
        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = lot_mock
            with pytest.raises(EcartInventaireSignificatif):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(), nouvelle_quantite=1,  # ecart ~99%
                    motif="Test", utilisateur=gestionnaire_stock,
                )


# ─── Ajustement manuel réel (DB) ──────────────────────────────────────────────

class TestServiceStockAjustementManuel:
    """Tests d'ajustement manuel avec un lot réel en base SQLite."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_ajustement_sous_seuil_reussit(self, service, gestionnaire_stock, db):
        """Ajustement de 3 % (< 5 %) → aucune exception, quantité mise à jour."""
        from tests.usine.usine_medicaments import UsineLot
        lot = UsineLot.create(quantite_disponible=100)
        resultat = service.ajuster_stock_manuel(
            lot_id=lot.id, nouvelle_quantite=97,
            motif="Casse constatée", utilisateur=gestionnaire_stock,
        )
        assert resultat.quantite_disponible == 97

    def test_ajustement_journalise_audit(self, service, gestionnaire_stock, db):
        """Un ajustement manuel doit appeler ServiceAudit.journaliser_ajustement_stock."""
        from tests.usine.usine_medicaments import UsineLot
        lot = UsineLot.create(quantite_disponible=100)
        with patch("gestion.audit.services.ServiceAudit") as mock_audit:
            service.ajuster_stock_manuel(
                lot_id=lot.id, nouvelle_quantite=97,
                motif="Casse rayon", utilisateur=gestionnaire_stock, adresse_ip="10.0.0.5",
            )
        mock_audit.return_value.journaliser_ajustement_stock.assert_called_once()
        appel = mock_audit.return_value.journaliser_ajustement_stock.call_args[1]
        assert appel["quantite_avant"] == 100
        assert appel["quantite_apres"] == 97

    def test_panne_audit_ne_bloque_pas_ajustement(self, service, gestionnaire_stock, db):
        """Une erreur dans ServiceAudit ne doit jamais empêcher l'ajustement."""
        from tests.usine.usine_medicaments import UsineLot
        lot = UsineLot.create(quantite_disponible=50)
        with patch("gestion.audit.services.ServiceAudit") as mock_audit:
            mock_audit.return_value.journaliser_ajustement_stock.side_effect = RuntimeError("DB indisponible")
            resultat = service.ajuster_stock_manuel(
                lot_id=lot.id, nouvelle_quantite=48,
                motif="Test résilience audit", utilisateur=gestionnaire_stock,
            )
        assert resultat.quantite_disponible == 48


# ─── Réception livraison ──────────────────────────────────────────────────────

class TestServiceStockReceptionLivraison:
    """Tests de receptionner_livraison()."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_reception_vide_retourne_zero_lots(self, service, gestionnaire_stock, db):
        resultat = service.receptionner_livraison(
            bon_commande_id=uuid.uuid4(), lignes_reception=[],
            utilisateur=gestionnaire_stock,
        )
        assert resultat["nombre"] == 0
        assert resultat["lots_crees"] == []

    def test_ligne_sans_medicament_id_leve_erreur(self, service, gestionnaire_stock, db):
        with pytest.raises(ValueError, match="manquants"):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[{"numero_lot": "LOT-001", "quantite": 10}],
                utilisateur=gestionnaire_stock,
            )

    def test_ligne_quantite_negative_leve_erreur(self, service, gestionnaire_stock, db):
        with pytest.raises(ValueError, match="strictement positive"):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[{
                    "medicament_id": uuid.uuid4(),
                    "numero_lot": "LOT-001",
                    "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                    "quantite": -5,
                    "prix_achat_unitaire": Decimal("500.00"),
                }],
                utilisateur=gestionnaire_stock,
            )

    def test_ligne_quantite_zero_leve_erreur(self, service, gestionnaire_stock, db):
        with pytest.raises(ValueError, match="strictement positive"):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[{
                    "medicament_id": uuid.uuid4(),
                    "numero_lot": "LOT-001",
                    "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                    "quantite": 0,
                    "prix_achat_unitaire": Decimal("500.00"),
                }],
                utilisateur=gestionnaire_stock,
            )

    def test_medicament_inexistant_leve_erreur(self, service, gestionnaire_stock, db):
        with pytest.raises(ValueError, match="introuvable"):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[{
                    "medicament_id": uuid.uuid4(),  # UUID inconnu
                    "numero_lot": "LOT-001",
                    "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                    "quantite": 10,
                    "prix_achat_unitaire": Decimal("500.00"),
                }],
                utilisateur=gestionnaire_stock,
            )

    def test_reception_valide_cree_lots_et_mouvements(self, service, gestionnaire_stock, db):
        """Une réception valide crée un Lot et un MouvementStock ENTREE."""
        from tests.usine.usine_medicaments import UsineMedicament
        medicament = UsineMedicament.create()
        bon_id = uuid.uuid4()

        resultat = service.receptionner_livraison(
            bon_commande_id=bon_id,
            lignes_reception=[{
                "medicament_id": medicament.id,
                "numero_lot": "LOT-TEST-001",
                "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                "quantite": 50,
                "prix_achat_unitaire": Decimal("450.00"),
                "emplacement_stockage": "Rayon B2",
            }],
            utilisateur=gestionnaire_stock,
        )

        assert resultat["nombre"] == 1
        lot_cree = resultat["lots_crees"][0]
        assert lot_cree.quantite_disponible == 50
        assert lot_cree.quantite_initiale == 50
        assert lot_cree.numero_lot == "LOT-TEST-001"

        # Vérification du mouvement ENTREE en base
        from gestion.stocks.models import MouvementStock
        mvt = MouvementStock.objects.filter(lot=lot_cree).first()
        assert mvt is not None
        assert mvt.quantite == 50

    def test_reception_multiple_lignes_atomique(self, service, gestionnaire_stock, db):
        """Plusieurs lignes → création atomique — si une échoue, aucun lot n'est créé."""
        from tests.usine.usine_medicaments import UsineMedicament
        medicament = UsineMedicament.create()

        with pytest.raises(ValueError):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[
                    {  # ligne valide
                        "medicament_id": medicament.id,
                        "numero_lot": "LOT-OK",
                        "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                        "quantite": 10,
                        "prix_achat_unitaire": Decimal("500.00"),
                    },
                    {  # ligne invalide → médicament inexistant
                        "medicament_id": uuid.uuid4(),
                        "numero_lot": "LOT-KO",
                        "date_peremption": datetime.date.today() + datetime.timedelta(days=365),
                        "quantite": 5,
                        "prix_achat_unitaire": Decimal("300.00"),
                    },
                ],
                utilisateur=gestionnaire_stock,
            )

        # Aucun lot ne doit avoir été créé (rollback atomique)
        from gestion.catalogue.models import Lot
        assert not Lot.objects.filter(numero_lot="LOT-OK").exists()


# ─── Inventaire ───────────────────────────────────────────────────────────────

class TestServiceStockInventaire:
    """Tests de la gestion des inventaires."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_demarrer_inventaire_requiert_gestionnaire_stock(self, service, caissier):
        from gestion.exceptions import PermissionRefusee
        caissier.a_permission_role = lambda r: False
        with pytest.raises(PermissionRefusee):
            service.demarrer_inventaire(utilisateur=caissier)

    def test_enregistrer_comptage_quantite_negative_leve_erreur(
        self, service, gestionnaire_stock, db
    ):
        inventaire_mock = MagicMock()
        inventaire_mock.statut = "en_cours"
        with patch("gestion.stocks.services.Inventaire") as mock_inv:
            mock_inv.objects.filter.return_value.first.return_value = inventaire_mock
            with pytest.raises(ValueError):
                service.enregistrer_comptage(
                    inventaire_id=uuid.uuid4(),
                    lot_id=uuid.uuid4(),
                    quantite_comptee=-1,
                    utilisateur=gestionnaire_stock,
                )



class TestServiceStockPermissions:
    """Tests des contrôles de permissions dans ServiceStock."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_ajuster_stock_requiert_gestionnaire_stock(self, service, caissier):
        """Un caissier ne peut pas ajuster le stock manuellement."""
        from gestion.exceptions import PermissionRefusee

        with pytest.raises(PermissionRefusee):
            service.ajuster_stock_manuel(
                lot_id=uuid.uuid4(),
                nouvelle_quantite=100,
                motif="Test",
                utilisateur=caissier,
            )

    def test_receptionner_livraison_requiert_gestionnaire_stock(self, service, caissier):
        """Un caissier ne peut pas réceptionner une livraison."""
        from gestion.exceptions import PermissionRefusee

        with pytest.raises(PermissionRefusee):
            service.receptionner_livraison(
                bon_commande_id=uuid.uuid4(),
                lignes_reception=[],
                utilisateur=caissier,
            )

    def test_ajuster_stock_lot_introuvable(self, service, gestionnaire_stock, db):
        """Ajuster un lot introuvable lève ValueError."""
        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = None

            with pytest.raises(ValueError, match="Lot introuvable"):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(),
                    nouvelle_quantite=100,
                    motif="Test",
                    utilisateur=gestionnaire_stock,
                )

    def test_ajuster_stock_lot_inactif_leve_erreur(self, service, gestionnaire_stock, db):
        """Ajuster un lot inactif lève LotInactif."""
        from gestion.exceptions import LotInactif

        lot_mock = MagicMock()
        lot_mock.est_actif = False
        lot_mock.numero_lot = "LOT-001"

        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = lot_mock

            with pytest.raises(LotInactif):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(),
                    nouvelle_quantite=100,
                    motif="Test",
                    utilisateur=gestionnaire_stock,
                )

    def test_ecart_important_requiert_pharmacien_adjoint(
        self, service, gestionnaire_stock
    ):
        """
        Un écart supérieur à SEUIL_ECART_APPROBATION
        nécessite le rôle pharmacien_adjoint.
        """
        from gestion.exceptions import EcartInventaireSignificatif

        lot_mock = MagicMock()
        lot_mock.est_actif = True
        lot_mock.quantite_disponible = 100
        lot_mock.medicament.nom = "Amoxicilline"
        lot_mock.numero_lot = "LOT-001"

        # Ajustement de 100 → 1 : écart de 99 % >> seuil de 5 %
        gestionnaire_stock.a_permission_role = (
            lambda r: r == "gestionnaire_stock"
            and r != "pharmacien_adjoint"
        )

        with patch("gestion.stocks.services.Lot") as mock_lot:
            mock_lot.objects.select_for_update.return_value.filter.return_value.first.return_value = lot_mock

            with pytest.raises(EcartInventaireSignificatif):
                service.ajuster_stock_manuel(
                    lot_id=uuid.uuid4(),
                    nouvelle_quantite=1,
                    motif="Test",
                    utilisateur=gestionnaire_stock,
                )

    def test_verifier_alertes_stock(self, service, db):
        """verifier_alertes_stock() retourne une liste d'alertes créées."""
        with patch("gestion.stocks.services.Medicament") as mock_med:
            mock_med.objects.filter.return_value.prefetch_related.return_value = []

            alertes = service.verifier_alertes_stock()
            assert isinstance(alertes, list)

    def test_calculer_besoins_reapprovisionnement(self, service, db):
        """calculer_besoins_reapprovisionnement() retourne une liste triée."""
        with patch("gestion.stocks.services.Medicament") as mock_med:
            mock_med.objects.filter.return_value.prefetch_related.return_value = []

            besoins = service.calculer_besoins_reapprovisionnement()
            assert isinstance(besoins, list)

    def test_seuil_ecart_approbation_est_5_pourcent(self, service):
        """Le seuil d'approbation est bien 5 %."""
        assert ServiceStock.SEUIL_ECART_APPROBATION == Decimal("5.00")

    def test_ajuster_stock_manuel_journalise_dans_audit(self, service, gestionnaire_stock, db):
        """
        CORRECTIF (audit 2026-07-21) : un ajustement manuel de stock doit être
        journalisé dans le journal d'audit réglementaire (JournalAudit), et
        non plus laissé au seul gestionnaire d'événement _sur_stock_ajuste
        (jamais déclenché en production faute de bus.publier() réel).
        """
        from tests.usine.usine_stocks import UsineLot

        lot = UsineLot(quantite_disponible=100)

        with patch("gestion.audit.services.ServiceAudit") as mock_service_audit:
            resultat = service.ajuster_stock_manuel(
                lot_id=lot.id,
                nouvelle_quantite=97,  # écart de 3 % — sous le seuil d'approbation
                motif="Casse constatée en rayon",
                utilisateur=gestionnaire_stock,
                adresse_ip="10.0.0.5",
            )

        assert resultat.quantite_disponible == 97
        mock_service_audit.return_value.journaliser_ajustement_stock.assert_called_once()
        appel = mock_service_audit.return_value.journaliser_ajustement_stock.call_args[1]
        assert appel["quantite_avant"] == 100
        assert appel["quantite_apres"] == 97
        assert appel["utilisateur"] == gestionnaire_stock
        assert appel["adresse_ip"] == "10.0.0.5"

    def test_ajuster_stock_manuel_ne_bloque_pas_si_audit_echoue(self, service, gestionnaire_stock, db):
        """Une panne du service d'audit ne doit jamais empêcher l'ajustement lui-même."""
        from tests.usine.usine_stocks import UsineLot

        lot = UsineLot(quantite_disponible=50)

        with patch("gestion.audit.services.ServiceAudit") as mock_service_audit:
            mock_service_audit.return_value.journaliser_ajustement_stock.side_effect = RuntimeError("DB indisponible")

            resultat = service.ajuster_stock_manuel(
                lot_id=lot.id,
                nouvelle_quantite=48,
                motif="Test résilience audit",
                utilisateur=gestionnaire_stock,
            )

        assert resultat.quantite_disponible == 48


class TestServiceStockInventaire:
    """Tests de la gestion des inventaires."""

    @pytest.fixture
    def service(self):
        return ServiceStock()

    def test_demarrer_inventaire_requiert_gestionnaire_stock(
        self, service, caissier
    ):
        """Seul un gestionnaire de stock peut démarrer un inventaire."""
        from gestion.exceptions import PermissionRefusee

        with pytest.raises(PermissionRefusee):
            service.demarrer_inventaire(utilisateur=caissier)

    def test_enregistrer_comptage_quantite_negative_leve_erreur(
        self, service, gestionnaire_stock, db
    ):
        """Une quantité comptée négative est invalide."""
        inventaire_mock = MagicMock()
        inventaire_mock.statut = "en_cours"

        with patch("gestion.stocks.services.Inventaire") as mock_inv:
            mock_inv.objects.filter.return_value.first.return_value = inventaire_mock

            with pytest.raises(ValueError):
                service.enregistrer_comptage(
                    inventaire_id=uuid.uuid4(),
                    lot_id=uuid.uuid4(),
                    quantite_comptee=-1,
                    utilisateur=gestionnaire_stock,
                )
