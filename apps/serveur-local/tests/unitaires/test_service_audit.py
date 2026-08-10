"""
tests/unitaires/test_service_audit.py
Tests unitaires du ServiceAudit et des gestionnaires automatiques.
Couverture cible : 100 % de gestion/audit/services.py
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unitaire


class TestServiceAudit:
    """Tests du service d'audit centralisé."""

    @pytest.fixture
    def service(self):
        from gestion.audit.services import ServiceAudit
        return ServiceAudit()

    def test_journaliser_vente_appelle_journal_audit(self, service):
        """journaliser_vente() délègue à JournalAudit.objects.journaliser()."""
        vente_mock = MagicMock()
        vente_mock.numero = "V-2024-000001"
        vente_mock.montant_total = Decimal("2400.00")
        vente_mock.mode_paiement = "especes"
        vente_mock.get_mode_paiement_display.return_value = "Espèces"
        vente_mock.client = None
        vente_mock.lignes.count.return_value = 3

        utilisateur = MagicMock(nom_complet="Kadiatou Traore")

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_vente(vente_mock, utilisateur)
            mock_journal.objects.journaliser.assert_called_once()

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "vente_creee"
        assert "V-2024-000001" in args["description"]
        assert args["severite"] == "info"

    def test_journaliser_vente_avec_client(self, service):
        """journaliser_vente() inclut le nom du client dans la description."""
        vente_mock = MagicMock()
        vente_mock.numero = "V-001"
        vente_mock.montant_total = Decimal("1000.00")
        vente_mock.get_mode_paiement_display.return_value = "Espèces"
        vente_mock.client.nom_complet = "Issa Sawadogo"
        vente_mock.lignes.count.return_value = 1

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_vente(vente_mock, MagicMock())

        args = mock_journal.objects.journaliser.call_args[1]
        assert "Issa Sawadogo" in args["description"]

    def test_journaliser_annulation_vente(self, service):
        """journaliser_annulation_vente() utilise la sévérité 'avertissement'."""
        vente_mock = MagicMock()
        vente_mock.numero = "V-002"
        vente_mock.montant_total = Decimal("2400.00")

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_annulation_vente(
                vente=vente_mock,
                motif="Erreur de saisie",
                utilisateur=MagicMock(),
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "vente_annulee"
        assert args["severite"] == "avertissement"
        assert "Erreur de saisie" in args["description"]

    def test_journaliser_ajustement_stock_ecart_significatif(self, service):
        """Un ajustement de > 10 % génère une alerte de sévérité 'alerte'."""
        lot_mock = MagicMock()
        lot_mock.medicament.nom = "Amoxicilline 500mg"
        lot_mock.numero_lot = "LOT-001"

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_ajustement_stock(
                lot=lot_mock,
                quantite_avant=100,
                quantite_apres=10,   # Écart de 90 % → très significatif
                motif="Perte",
                utilisateur=MagicMock(),
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["severite"] == "alerte"

    def test_journaliser_ajustement_stock_ecart_faible(self, service):
        """Un ajustement de ≤ 10 % génère une sévérité 'avertissement'."""
        lot_mock = MagicMock()
        lot_mock.medicament.nom = "Paracétamol 500mg"
        lot_mock.numero_lot = "LOT-002"

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_ajustement_stock(
                lot=lot_mock,
                quantite_avant=100,
                quantite_apres=99,   # Écart de 1 % → faible
                motif="Casse",
                utilisateur=MagicMock(),
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["severite"] == "avertissement"

    def test_journaliser_connexion_reussie(self, service):
        """journaliser_connexion() avec succes=True utilise le type 'connexion_reussie'."""
        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_connexion(
                email="titulaire@pharmapp.bf",
                succes=True,
                utilisateur=MagicMock(),
                adresse_ip="192.168.1.1",
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "connexion_reussie"
        assert args["severite"] == "info"

    def test_journaliser_connexion_echouee(self, service):
        """journaliser_connexion() avec succes=False utilise 'connexion_echouee'."""
        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            with patch.object(service, "_compter_echecs_recents", return_value=1):
                service.journaliser_connexion(
                    email="inconnu@attaque.com",
                    succes=False,
                    raison_echec="Mot de passe incorrect",
                    adresse_ip="10.0.0.1",
                )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "connexion_echouee"
        assert args["severite"] == "alerte"

    def test_journaliser_connexion_echouee_repetes_critique(self, service):
        """5+ échecs de connexion → sévérité 'critique'."""
        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            with patch.object(service, "_compter_echecs_recents", return_value=10):
                service.journaliser_connexion(
                    email="victime@pharmapp.bf",
                    succes=False,
                    adresse_ip="1.2.3.4",
                )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["severite"] == "critique"

    def test_journaliser_acces_ordonnance(self, service):
        """journaliser_acces_ordonnance() utilise la sévérité 'alerte' (données médicales)."""
        ordonnance_mock = MagicMock()
        ordonnance_mock.numero_interne = "ORD-2024-001"
        ordonnance_mock.client.nom_complet = "Patient Test"

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_acces_ordonnance(
                ordonnance=ordonnance_mock,
                utilisateur=MagicMock(),
                adresse_ip="192.168.1.5",
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "acces_sensible"
        assert args["severite"] == "alerte"

    def test_journaliser_produit_controle_toujours_critique(self, service):
        """Toute opération sur un produit contrôlé est de sévérité 'critique'."""
        registre_mock = MagicMock()
        registre_mock.medicament.nom = "Morphine 10mg"
        registre_mock.quantite_mouvement = 5
        registre_mock.unite = "ampoules"
        registre_mock.numero_lot_fabricant = "LOT-MORPH-001"

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            service.journaliser_produit_controle(
                registre=registre_mock,
                type_mouvement="sortie",
                utilisateur=MagicMock(),
            )

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["severite"] == "critique"
        assert args["type_action"] == "produit_controle_mouvement"

    def test_rapport_activite_structure(self, service, db):
        """rapport_activite() retourne un dict avec toutes les clés attendues."""
        from datetime import date
        import datetime

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            mock_journal.objects.filter.return_value = MagicMock()
            mock_qs = MagicMock()
            mock_journal.objects.filter.return_value = mock_qs
            mock_qs.values.return_value.annotate.return_value.values_list.return_value = []

            rapport = service.rapport_activite(
                date_debut=date.today(),
                date_fin=date.today(),
            )

        assert "total_connexions" in rapport
        assert "connexions_echouees" in rapport
        assert "total_ventes" in rapport
        assert "ajustements_stock" in rapport
        assert "acces_sensibles" in rapport
        assert "produits_controles" in rapport
        assert "par_severite" in rapport


class TestGestionnairesAuditAutomatiques:
    """Tests des gestionnaires automatiques enregistrés sur le bus d'événements."""

    def test_enregistrer_gestionnaires_audit_enregistre_4_gestionnaires(self):
        """enregistrer_gestionnaires_audit() enregistre exactement 4 gestionnaires."""
        from infrastructure.bus_evenements.bus import BusEvenements, RegistreGestionnaires
        from gestion.audit.services import enregistrer_gestionnaires_audit

        registre = RegistreGestionnaires()
        registre.tout_effacer()
        bus = BusEvenements(registre=registre)

        enregistrer_gestionnaires_audit(bus)

        assert registre.nombre_gestionnaires == 4
        registre.tout_effacer()

    def test_sur_vente_creee_journalise(self):
        """_sur_vente_creee() crée une entrée d'audit pour chaque vente."""
        from gestion.audit.services import _sur_vente_creee
        from infrastructure.bus_evenements.bus import EvenementVenteCreee

        evt = EvenementVenteCreee(
            numero_vente="V-2024-001",
            montant_total="2400.00",
            mode_paiement="especes",
        )

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            _sur_vente_creee(evt)

        mock_journal.objects.journaliser.assert_called_once()
        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "vente_creee"
        assert "V-2024-001" in args["description"]

    def test_sur_vente_annulee_journalise(self):
        """_sur_vente_annulee() crée une entrée d'audit pour chaque annulation."""
        from gestion.audit.services import _sur_vente_annulee
        from infrastructure.bus_evenements.bus import EvenementVenteAnnulee

        evt = EvenementVenteAnnulee(
            numero_vente="V-2024-005",
            motif_annulation="Demande client",
        )

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            _sur_vente_annulee(evt)

        mock_journal.objects.journaliser.assert_called_once()
        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "vente_annulee"

    def test_sur_stock_ajuste_journalise(self):
        """_sur_stock_ajuste() crée une entrée d'audit pour chaque ajustement."""
        from gestion.audit.services import _sur_stock_ajuste
        from infrastructure.bus_evenements.bus import EvenementStockAjuste

        evt = EvenementStockAjuste(
            nom_medicament="Amoxicilline",
            quantite_avant=100,
            quantite_apres=95,
            motif="Périmés écartés",
        )

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            _sur_stock_ajuste(evt)

        mock_journal.objects.journaliser.assert_called_once()

    def test_sur_connexion_succes_journalise(self):
        """_sur_connexion() journalise les connexions réussies."""
        from gestion.audit.services import _sur_connexion
        from infrastructure.bus_evenements.bus import EvenementConnexion

        evt = EvenementConnexion(
            email_tente="titulaire@pharmapp.bf",
            succes=True,
        )

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            _sur_connexion(evt)

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "connexion_reussie"

    def test_sur_connexion_echec_journalise(self):
        """_sur_connexion() journalise les connexions échouées."""
        from gestion.audit.services import _sur_connexion
        from infrastructure.bus_evenements.bus import EvenementConnexion

        evt = EvenementConnexion(
            email_tente="attaquant@evil.com",
            succes=False,
            raison_echec="Compte inexistant",
            adresse_ip="1.2.3.4",
        )

        with patch("gestion.audit.services.JournalAudit") as mock_journal:
            _sur_connexion(evt)

        args = mock_journal.objects.journaliser.call_args[1]
        assert args["type_action"] == "connexion_echouee"
        assert args["severite"] == "alerte"


class TestIntegriteJournalAuditReel:
    """
    Tests d'intégrité sur des entrées RÉELLEMENT PERSISTÉES (aucun mock de
    JournalAudit) — ajoutés suite à l'audit du 2026-07-21.

    Avant correctif, JournalAuditManager.journaliser() calculait le hash avec
    un timezone.now() distinct de celui affecté à cree_le par auto_now_add,
    rendant verifier_integrite() perpétuellement False. Cette classe est la
    seule de la suite à exercer le calcul de hash réel de bout en bout —
    c'est précisément le test qui manquait et qui aurait révélé l'anomalie.
    """

    @pytest.fixture
    def service(self):
        from gestion.audit.services import ServiceAudit
        return ServiceAudit()

    def test_verifier_integrite_entree_reelle_valide(self, db):
        """Une entrée créée normalement doit être reconnue comme intègre."""
        from gestion.audit.models import JournalAudit

        entree = JournalAudit.objects.journaliser(
            type_action="connexion_reussie",
            description="Connexion réussie — titulaire@pharmapp.bf",
            severite="info",
        )

        # Relecture depuis la base : garantit qu'on vérifie bien la valeur
        # persistée de cree_le, pas l'objet Python encore en mémoire.
        entree_relue = JournalAudit.objects.get(pk=entree.pk)
        assert entree_relue.verifier_integrite() is True

    def test_verifier_integrite_detecte_alteration(self, db):
        """Toute modification du contenu doit invalider l'empreinte."""
        from gestion.audit.models import JournalAudit

        entree = JournalAudit.objects.journaliser(
            type_action="vente_annulee",
            description="Vente V-0001 ANNULÉE — Motif : erreur de saisie",
            severite="avertissement",
        )

        # Altération directe en base, en contournant save() (qui bloquerait
        # la modification) — simule une falsification externe au journal.
        JournalAudit.objects.filter(pk=entree.pk).update(
            description="Vente V-0001 ANNULÉE — Motif : fraude dissimulée"
        )
        entree_alteree = JournalAudit.objects.get(pk=entree.pk)

        assert entree_alteree.verifier_integrite() is False

    def test_verifier_integrite_journal_service_sur_entrees_reelles(self, service, db):
        """ServiceAudit.verifier_integrite_journal() doit rapporter 0 corrompue
        sur un journal composé uniquement d'entrées saines."""
        service.journaliser_connexion(email="a@pharmapp.bf", succes=True)
        service.journaliser_connexion(email="b@pharmapp.bf", succes=False, raison_echec="mdp invalide")

        resultat = service.verifier_integrite_journal()

        assert resultat["total"] == 2
        assert resultat["corrompues"] == []
        assert resultat["integrite_ok"] is True
