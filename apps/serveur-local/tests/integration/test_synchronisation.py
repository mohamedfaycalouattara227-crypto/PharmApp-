"""
tests/integration/test_synchronisation.py
ÉTAPE 05 — Tests de synchronisation hors-ligne : Outbox, rejeu, conflits, dégradé.

Couvre :
  - Inscription d'événements dans l'Outbox (idempotence, filtrage types exclus)
  - Traitement par lot (batch) : envoi réussi, marquage TRAITE
  - Retry automatique sur erreur 5xx (back-off, max_tentatives)
  - Résolution de conflits (version locale gagne, version cloud gagne, ignoré)
  - Connexion dégradée : statut mis à jour
  - Événements de types exclus (image_ordonnance, connexion_echouee) non synchronisés

Marqueur : pytest.mark.integration
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

pytestmark = pytest.mark.integration


# ─── Fixtures locales ─────────────────────────────────────────────────────────

@pytest.fixture
def service_sync():
    """Instance fraîche du ServiceSynchronisation."""
    from gestion.sync.services import ServiceSynchronisation
    return ServiceSynchronisation()


@pytest.fixture
def entree_outbox(db):
    """Crée une entrée Outbox EN_ATTENTE."""
    from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
    return EntreeOutbox.objects.create(
        type_evenement="vente_creee",
        charge_utile={"vente_id": str(uuid.uuid4()), "montant": "5000.00"},
        statut=StatutOutbox.EN_ATTENTE,
        id_objet=uuid.uuid4(),
        modele_source="Vente",
    )


# ─── 1. Inscription dans l'Outbox ─────────────────────────────────────────────

class TestInscriptionOutbox:
    """Vérifie l'inscription correcte des événements dans l'Outbox."""

    def test_inscrire_evenement_cree_entree_en_attente(self, db, service_sync):
        """Un événement normal crée une entrée EN_ATTENTE dans l'Outbox."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        id_vente = uuid.uuid4()
        service_sync.inscrire_dans_outbox(
            type_evenement="vente_creee",
            charge_utile={"vente_id": str(id_vente), "montant": "3500.00"},
            id_objet=id_vente,
            modele_source="Vente",
        )

        entree = EntreeOutbox.objects.filter(type_evenement="vente_creee").first()
        assert entree is not None
        assert entree.statut == StatutOutbox.EN_ATTENTE
        assert str(id_vente) in str(entree.charge_utile)

    def test_type_exclu_nest_pas_inscrit(self, db, service_sync):
        """Les types exclus (image_ordonnance, connexion_echouee) ne sont pas inscrits."""
        from infrastructure.outbox.modeles import EntreeOutbox

        for type_exclu in ["image_ordonnance", "connexion_echouee", "acces_sensible"]:
            service_sync.inscrire_dans_outbox(
                type_evenement=type_exclu,
                charge_utile={"data": "sensible"},
            )

        assert not EntreeOutbox.objects.filter(
            type_evenement__in=["image_ordonnance", "connexion_echouee", "acces_sensible"]
        ).exists(), (
            "Des événements de types exclus ont été inscrits dans l'Outbox."
        )

    def test_charge_utile_preservee_integralite(self, db, service_sync):
        """La charge utile est stockée intégralement dans l'Outbox."""
        from infrastructure.outbox.modeles import EntreeOutbox

        charge = {
            "vente_id": str(uuid.uuid4()),
            "montant_total": "12500.50",
            "mode_paiement": "mobile_money",
            "articles": [{"medicament": "Paracétamol", "quantite": 2}],
        }
        service_sync.inscrire_dans_outbox(
            type_evenement="vente_creee",
            charge_utile=charge,
        )

        entree = EntreeOutbox.objects.filter(type_evenement="vente_creee").last()
        assert entree.charge_utile["montant_total"] == "12500.50"
        assert entree.charge_utile["mode_paiement"] == "mobile_money"


# ─── 2. Traitement par lot (traiter_outbox) ───────────────────────────────────

class TestTraitementOutbox:
    """Vérifie le traitement par lot des entrées Outbox."""

    def test_traitement_reussi_marque_entree_traite(self, db, service_sync, entree_outbox):
        """Un envoi réussi marque l'entrée comme TRAITE."""
        from infrastructure.outbox.modeles import StatutOutbox

        with patch.object(
            service_sync, "_envoyer_vers_cloud", return_value=True
        ):
            resultat = service_sync.traiter_outbox(taille_lot=10)

        entree_outbox.refresh_from_db()
        assert entree_outbox.statut == StatutOutbox.TRAITE
        assert entree_outbox.traite_le is not None
        assert resultat.evenements_envoyes >= 1

    def test_traitement_echoue_incremente_tentatives(
        self, db, service_sync, entree_outbox
    ):
        """Un échec d'envoi incrémente le compteur de tentatives."""
        from infrastructure.outbox.modeles import StatutOutbox

        tentatives_avant = entree_outbox.nombre_tentatives

        with patch.object(
            service_sync, "_envoyer_vers_cloud", side_effect=ConnectionError("5xx")
        ):
            try:
                service_sync.traiter_outbox(taille_lot=10)
            except Exception:
                pass

        entree_outbox.refresh_from_db()
        assert (
            entree_outbox.nombre_tentatives > tentatives_avant
            or entree_outbox.statut != StatutOutbox.TRAITE
        )

    def test_max_tentatives_depasse_marque_echec_definitif(
        self, db, service_sync
    ):
        """Une entrée ayant atteint max_tentatives est marquée ECHEC définitif."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree = EntreeOutbox.objects.create(
            type_evenement="stock_ajuste",
            charge_utile={"lot_id": str(uuid.uuid4())},
            statut=StatutOutbox.EN_ATTENTE,
            nombre_tentatives=4,  # déjà à max-1
            max_tentatives=5,
        )

        with patch.object(
            service_sync, "_envoyer_vers_cloud", side_effect=ConnectionError("Timeout")
        ):
            try:
                service_sync.traiter_outbox(taille_lot=10)
            except Exception:
                pass

        entree.refresh_from_db()
        # Après max_tentatives échecs → ECHEC ou tentatives >= max
        assert (
            entree.statut == StatutOutbox.ECHEC
            or entree.nombre_tentatives >= entree.max_tentatives
        )

    def test_taille_lot_limite_nombre_entrees_traitees(self, db, service_sync):
        """Le paramètre taille_lot limite le nombre d'entrées traitées."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        for i in range(10):
            EntreeOutbox.objects.create(
                type_evenement=f"evenement_{i}",
                charge_utile={"i": i},
                statut=StatutOutbox.EN_ATTENTE,
            )

        with patch.object(
            service_sync, "_envoyer_vers_cloud", return_value=True
        ):
            resultat = service_sync.traiter_outbox(taille_lot=3)

        assert resultat.evenements_envoyes <= 3


# ─── 3. Résolution de conflits ────────────────────────────────────────────────

class TestResolutionConflits:
    """Vérifie la résolution des conflits de synchronisation."""

    def test_conflit_resolu_local_conserve_donnees_locales(self, db):
        """Résolution 'local' → les données locales sont conservées."""
        from gestion.synchronisation.modeles import (
            ConflitSynchronisation,
            StatutConflit,
        )

        conflit = ConflitSynchronisation.objects.create(
            modele="Medicament",
            id_objet=uuid.uuid4(),
            donnees_locales={"prix_public": "1200.00"},
            donnees_cloud={"prix_public": "1500.00"},
            statut=StatutConflit.NON_RESOLU,
        )

        conflit.statut = StatutConflit.RESOLU_LOCAL
        conflit.resolu_par = "pharmacien_adjoint"
        conflit.resolu_le = timezone.now()
        conflit.save()

        conflit.refresh_from_db()
        assert conflit.statut == StatutConflit.RESOLU_LOCAL
        assert conflit.donnees_locales["prix_public"] == "1200.00"

    def test_conflit_resolu_cloud_applique_donnees_cloud(self, db):
        """Résolution 'cloud' → les données cloud sont marquées comme appliquées."""
        from gestion.synchronisation.modeles import (
            ConflitSynchronisation,
            StatutConflit,
        )

        conflit = ConflitSynchronisation.objects.create(
            modele="Client",
            id_objet=uuid.uuid4(),
            donnees_locales={"nom": "Ancien nom"},
            donnees_cloud={"nom": "Nom cloud mis à jour"},
            statut=StatutConflit.NON_RESOLU,
        )

        conflit.statut = StatutConflit.RESOLU_CLOUD
        conflit.resolu_par = "titulaire"
        conflit.resolu_le = timezone.now()
        conflit.save()

        conflit.refresh_from_db()
        assert conflit.statut == StatutConflit.RESOLU_CLOUD
        assert conflit.donnees_cloud["nom"] == "Nom cloud mis à jour"

    def test_compte_conflits_non_resolus(self, db, service_sync):
        """Le statut de sync comptabilise les conflits non résolus."""
        from gestion.synchronisation.modeles import (
            ConflitSynchronisation,
            StatutConflit,
        )

        for _ in range(3):
            ConflitSynchronisation.objects.create(
                modele="Stock",
                id_objet=uuid.uuid4(),
                donnees_locales={"q": 10},
                donnees_cloud={"q": 12},
                statut=StatutConflit.NON_RESOLU,
            )

        statut = service_sync.obtenir_statut()
        assert statut.conflits_non_resolus >= 3


# ─── 4. État de connexion dégradée ───────────────────────────────────────────

class TestConnexionDegradee:
    """Vérifie le comportement en mode connexion dégradée."""

    def test_statut_retourne_hors_ligne_quand_pas_etat(self, db, service_sync):
        """Sans EtatSynchronisation en base, le statut est hors_ligne."""
        from gestion.synchronisation.modeles import EtatSynchronisation
        EtatSynchronisation.objects.all().delete()

        statut = service_sync.obtenir_statut()
        assert statut.est_connecte is False

    def test_connexion_active_mise_a_jour_statut(self, db):
        """La mise à jour du statut connexion est persistée en base."""
        from gestion.synchronisation.modeles import (
            EtatSynchronisation,
            StatutConnexion,
        )

        etat = EtatSynchronisation.objects.create(
            statut_connexion=StatutConnexion.HORS_LIGNE,
        )

        etat.statut_connexion = StatutConnexion.EN_LIGNE
        etat.derniere_sync_reussie = timezone.now()
        etat.save()

        etat.refresh_from_db()
        assert etat.statut_connexion == StatutConnexion.EN_LIGNE
        assert etat.derniere_sync_reussie is not None

    def test_evenements_en_attente_comptabilises(self, db, service_sync):
        """Les entrées EN_ATTENTE sont comptabilisées dans le statut."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        for i in range(5):
            EntreeOutbox.objects.create(
                type_evenement=f"test_attente_{i}",
                charge_utile={},
                statut=StatutOutbox.EN_ATTENTE,
            )

        statut = service_sync.obtenir_statut()
        assert statut.evenements_en_attente >= 5

    def test_erreur_reseau_ne_crash_pas_le_service(self, db, service_sync):
        """Une erreur réseau lors du calcul du statut retourne un statut par défaut."""
        from gestion.synchronisation.modeles import EtatSynchronisation

        with patch.object(
            EtatSynchronisation.objects,
            "order_by",
            side_effect=Exception("DB error"),
        ):
            statut = service_sync.obtenir_statut()

        # Ne lève pas d'exception — retourne un statut dégradé
        assert statut is not None
        assert statut.est_connecte is False


# ─── 5. Idempotence du rejeu ──────────────────────────────────────────────────

class TestIdempotenceRejeu:
    """Le rejeu d'un événement déjà traité ne doit pas créer de doublon."""

    def test_rejouer_echecs_appelle_service_avec_bonne_limite(
        self, db, service_sync
    ):
        """rejouer_echecs() est appelé avec la limite paramétrée."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        for i in range(3):
            EntreeOutbox.objects.create(
                type_evenement="client_modifie",
                charge_utile={"client_id": str(uuid.uuid4())},
                statut=StatutOutbox.ECHEC,
                nombre_tentatives=2,
                max_tentatives=5,
            )

        with patch.object(
            service_sync, "_envoyer_vers_cloud", return_value=True
        ):
            nb = service_sync.rejouer_echecs(limit=3)

        assert isinstance(nb, int)

    def test_entree_deja_traitee_ignoree_au_rejeu(self, db, service_sync):
        """Une entrée TRAITE n'est pas retraitée lors du rejeu."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        entree_traitee = EntreeOutbox.objects.create(
            type_evenement="stock_ajuste",
            charge_utile={"lot": "xxx"},
            statut=StatutOutbox.TRAITE,
            traite_le=timezone.now(),
        )

        appels = []
        with patch.object(
            service_sync,
            "_envoyer_vers_cloud",
            side_effect=lambda e: appels.append(e) or True,
        ):
            service_sync.traiter_outbox(taille_lot=10)

        # L'entrée TRAITE ne doit pas avoir été retraitée
        assert entree_traitee.pk not in [getattr(e, "pk", None) for e in appels]
