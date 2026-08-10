"""
tests/unitaires/test_outbox.py
Tests unitaires du pattern Outbox transactionnel.
Couverture cible : 100 % des modules infrastructure/outbox/
"""

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unitaire


class TestEntreeOutboxModele:
    """Tests du modèle EntreeOutbox (avec DB SQLite en mémoire)."""

    @pytest.fixture(autouse=True)
    def vider_outbox(self, db):
        from infrastructure.outbox.modeles import EntreeOutbox
        EntreeOutbox.objects.all().delete()

    def test_creer_entree_en_attente(self, db):
        """creer() crée une entrée avec le statut EN_ATTENTE par défaut."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer(
            type_evenement="EvenementVenteCreee",
            charge_utile={"id_vente": str(uuid.uuid4()), "montant": "2400.00"},
        )

        assert entree.pk is not None
        assert entree.statut == StatutOutbox.EN_ATTENTE
        assert entree.nombre_tentatives == 0

    def test_creer_entree_avec_metadata(self, db):
        """creer() accepte tous les paramètres optionnels."""
        from infrastructure.outbox.modeles import EntreeOutbox

        id_objet = uuid.uuid4()
        id_user = uuid.uuid4()
        entree = EntreeOutbox.creer(
            type_evenement="EvenementVenteCreee",
            charge_utile={"numero": "V-001"},
            id_objet=id_objet,
            modele_source="Vente",
            id_utilisateur=id_user,
            max_tentatives=3,
        )

        assert entree.id_objet == id_objet
        assert entree.modele_source == "Vente"
        assert entree.id_utilisateur == id_user
        assert entree.max_tentatives == 3

    def test_marquer_en_cours(self, db):
        """marquer_en_cours() incrémente le compteur de tentatives."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1})
        entree.marquer_en_cours()

        entree.refresh_from_db()
        assert entree.statut == StatutOutbox.EN_COURS
        assert entree.nombre_tentatives == 1

    def test_marquer_traite(self, db):
        """marquer_traite() finalise l'entrée avec la date de traitement."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1})
        entree.marquer_en_cours()
        entree.marquer_traite()

        entree.refresh_from_db()
        assert entree.statut == StatutOutbox.TRAITE
        assert entree.traite_le is not None

    def test_marquer_echec_avec_backoff(self, db):
        """marquer_echec() planifie la prochaine tentative avec backoff exponentiel."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1}, max_tentatives=3)
        entree.marquer_en_cours()
        entree.marquer_echec("Erreur réseau")

        entree.refresh_from_db()
        assert entree.statut == StatutOutbox.EN_ATTENTE  # Pas encore définitif
        assert entree.erreur_message == "Erreur réseau"
        assert entree.prochaine_tentative is not None

    def test_marquer_echec_definitif_apres_max_tentatives(self, db):
        """Après max_tentatives, le statut passe à ECHEC définitif."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1}, max_tentatives=2)
        entree.nombre_tentatives = 2  # Simuler que max est atteint
        entree.save(update_fields=["nombre_tentatives"])

        entree.marquer_echec("Erreur finale")

        entree.refresh_from_db()
        assert entree.statut == StatutOutbox.ECHEC
        assert entree.prochaine_tentative is None

    def test_rejouer_entree_en_echec(self, db):
        """rejouer() remet une entrée ECHEC en EN_ATTENTE."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1}, max_tentatives=1)
        entree.statut = StatutOutbox.ECHEC
        entree.nombre_tentatives = 1
        entree.save(update_fields=["statut", "nombre_tentatives"])

        entree.rejouer()

        entree.refresh_from_db()
        assert entree.statut == StatutOutbox.EN_ATTENTE
        assert entree.nombre_tentatives == 0
        assert entree.erreur_message == ""

    def test_rejouer_entree_non_echouee_leve_erreur(self, db):
        """rejouer() lève ValueError si l'entrée n'est pas en ECHEC."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1})  # EN_ATTENTE

        with pytest.raises(ValueError, match="Impossible de rejouer"):
            entree.rejouer()

    def test_peut_etre_rejoue_seulement_si_echec(self, db):
        """peut_etre_rejoue est True uniquement pour le statut ECHEC."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.creer("Evt", {"x": 1})
        assert not entree.peut_etre_rejoue

        entree.statut = StatutOutbox.ECHEC
        assert entree.peut_etre_rejoue

    def test_en_attente_filtre_prochaine_tentative(self, db):
        """en_attente() ne retourne que les entrées dont prochaine_tentative ≤ now."""
        from infrastructure.outbox.modeles import EntreeOutbox
        from django.utils import timezone

        # Entrée prête
        e1 = EntreeOutbox.creer("Evt1", {})
        # Entrée planifiée dans le futur
        e2 = EntreeOutbox.creer("Evt2", {})
        e2.prochaine_tentative = timezone.now() + datetime.timedelta(hours=1)
        e2.save(update_fields=["prochaine_tentative"])

        prets = list(EntreeOutbox.en_attente())
        ids = [e.id for e in prets]
        assert e1.id in ids
        assert e2.id not in ids

    def test_str_representation(self, db):
        """__str__ retourne une représentation lisible."""
        from infrastructure.outbox.modeles import EntreeOutbox
        entree = EntreeOutbox.creer("EvenementVenteCreee", {"x": 1})
        assert "EvenementVenteCreee" in str(entree)
        assert "en_attente" in str(entree)

    def test_backoff_exponentiel_progression(self, db):
        """Le délai de backoff suit une progression exponentielle."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        from django.utils import timezone

        delais = []
        for i in range(4):
            entree = EntreeOutbox.creer("Evt", {}, max_tentatives=10)
            entree.nombre_tentatives = i
            entree.save(update_fields=["nombre_tentatives"])

            avant = timezone.now()
            entree.marquer_echec("err")
            entree.refresh_from_db()

            if entree.prochaine_tentative:
                delai = (entree.prochaine_tentative - avant).total_seconds() / 60
                delais.append(round(delai))

        # Les délais doivent être croissants (1, 2, 4, 8 minutes)
        for i in range(1, len(delais)):
            assert delais[i] > delais[i - 1]


class TestProcesseurOutbox:
    """Tests du processeur Outbox."""

    @pytest.fixture(autouse=True)
    def vider_outbox(self, db):
        from infrastructure.outbox.modeles import EntreeOutbox
        EntreeOutbox.objects.all().delete()

    def test_traiter_lot_vide(self, db):
        """traiter_lot() retourne zéro si l'Outbox est vide."""
        from infrastructure.outbox.processeur import ProcesseurOutbox

        rapport = ProcesseurOutbox().traiter_lot()

        assert rapport["traites"] == 0
        assert rapport["echecs"] == 0
        assert rapport["total"] == 0

    def test_traiter_evenement_inconnu_leve_erreur(self, db):
        """Un type d'événement inconnu est traité comme ECHEC."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        from infrastructure.outbox.processeur import ProcesseurOutbox

        EntreeOutbox.creer("EvenementInexistant", {"x": 1})

        rapport = ProcesseurOutbox().traiter_lot()

        assert rapport["echecs"] == 1
        assert rapport["traites"] == 0

    def test_statistiques(self, db):
        """statistiques() retourne un dict avec les comptages par statut."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        from infrastructure.outbox.processeur import ProcesseurOutbox

        EntreeOutbox.creer("Evt1", {})
        EntreeOutbox.creer("Evt2", {})
        e = EntreeOutbox.creer("Evt3", {})
        e.statut = StatutOutbox.TRAITE
        e.save(update_fields=["statut"])

        stats = ProcesseurOutbox.statistiques()

        assert stats.get(StatutOutbox.EN_ATTENTE, 0) == 2
        assert stats.get(StatutOutbox.TRAITE, 0) == 1

    def test_router_evenement_inconnu_leve_value_error(self, db):
        """_router_evenement lève ValueError pour un type inconnu."""
        from infrastructure.outbox.modeles import EntreeOutbox
        from infrastructure.outbox.processeur import ProcesseurOutbox

        entree = EntreeOutbox.creer("TypeInconnu", {})
        proc = ProcesseurOutbox()

        with pytest.raises(ValueError, match="non reconnu"):
            proc._router_evenement(entree)
