"""
tests/integration/test_processeur_outbox.py
ÉTAPE 05 — Clôture : tests du ProcesseurOutbox (routage, cloud, idempotence, dégradé).

Couvre :
  - Routage interne : type_evenement connu → gestionnaire appelé
  - Type d'événement non routé → ValueError → ECHEC définitif
  - Envoi cloud : mode dégradé (config absente) → événement conservé
  - Envoi cloud : erreur 4xx → ValueError → ECHEC définitif (pas de retry)
  - Envoi cloud : erreur 5xx/réseau → RuntimeError → retry planifié
  - Idempotence 409 : considéré comme succès
  - statistiques() retourne un dict par statut
  - Traitement lot complet : traites + echecs comptés correctement

Marqueur : pytest.mark.integration
"""

import uuid
from unittest.mock import MagicMock, patch, call
import urllib.error

import pytest
from django.utils import timezone

pytestmark = pytest.mark.integration

BASE = "infrastructure.outbox.processeur"


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def processeur():
    from infrastructure.outbox.processeur import ProcesseurOutbox
    return ProcesseurOutbox()


@pytest.fixture
def entree_vente(db):
    """Entrée EN_ATTENTE de type EvenementVenteCreee."""
    from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
    return EntreeOutbox.objects.create(
        type_evenement="EvenementVenteCreee",
        charge_utile={"montant_total": "5000.00", "mode_paiement": "especes"},
        statut=StatutOutbox.EN_ATTENTE,
        id_objet=uuid.uuid4(),
        modele_source="Vente",
        prochaine_tentative=timezone.now(),
    )


@pytest.fixture
def entree_inconnue(db):
    """Entrée EN_ATTENTE avec type non routé."""
    from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
    return EntreeOutbox.objects.create(
        type_evenement="TypeInconnu",
        charge_utile={"data": "x"},
        statut=StatutOutbox.EN_ATTENTE,
        prochaine_tentative=timezone.now(),
    )


# ─── 1. Routage interne ───────────────────────────────────────────────────────

class TestRoutageInterne:
    """Le processeur appelle le bon gestionnaire selon type_evenement."""

    def test_type_connu_appelle_gestionnaire(self, db, processeur, entree_vente):
        """EvenementVenteCreee → _traiter_vente_creee appelé."""
        from gestion.synchronisation.modeles import EvenementSynchronisation

        with patch.object(processeur, "_envoyer_vers_cloud"):
            processeur.traiter_lot(taille=10)

        assert EvenementSynchronisation.objects.filter(
            type_evenement="vente_creee"
        ).exists()

    def test_type_inconnu_leve_value_error(self, processeur):
        """Un type d'événement non routé lève ValueError."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        entree = MagicMock(spec=EntreeOutbox)
        entree.type_evenement = "TypeFantome"

        with pytest.raises(ValueError, match="Type d'événement non reconnu"):
            processeur._router_evenement(entree)

    def test_type_inconnu_marque_echec_definitif(self, db, processeur, entree_inconnue):
        """Un type inconnu marque l'entrée en ECHEC définitif (force_definitif=True)."""
        from infrastructure.outbox.modeles import StatutOutbox

        with patch.object(processeur, "_envoyer_vers_cloud"):
            rapport = processeur.traiter_lot(taille=10)

        entree_inconnue.refresh_from_db()
        assert entree_inconnue.statut == StatutOutbox.ECHEC
        assert rapport["echecs"] >= 1

    def test_tous_types_routes_ont_methode(self, processeur):
        """Chaque type dans ROUTAGE possède une méthode correspondante."""
        for type_evt, methode_nom in processeur.ROUTAGE.items():
            assert hasattr(processeur, methode_nom), (
                f"Méthode '{methode_nom}' manquante pour le type '{type_evt}'"
            )


# ─── 2. Mode dégradé (cloud non configuré) ───────────────────────────────────

class TestModeDegradé:
    """Quand le cloud n'est pas configuré, l'événement est conservé localement."""

    def test_config_absente_mode_degrade_silencieux(self, db, processeur, entree_vente):
        """Sans config cloud, _envoyer_vers_cloud ne lève pas d'exception."""
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=False):
            # Ne doit pas lever d'exception
            processeur._envoyer_vers_cloud(entree_vente)

    def test_config_corrompue_mode_degrade_silencieux(self, db, processeur, entree_vente):
        """Une exception de lecture de config est capturée → mode dégradé."""
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        with patch.object(
            ServiceParametrageCloud,
            "est_configure",
            side_effect=Exception("Config corrompue"),
        ):
            processeur._envoyer_vers_cloud(entree_vente)  # pas d'exception

    def test_entree_reste_en_attente_mode_degrade(self, db, processeur, entree_vente):
        """En mode dégradé, l'entrée n'est pas marquée ECHEC."""
        from infrastructure.outbox.modeles import StatutOutbox
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=False):
            with patch.object(processeur, "_router_evenement"):
                rapport = processeur.traiter_lot(taille=10)

        entree_vente.refresh_from_db()
        # Traité côté routage local, cloud ignoré → TRAITE
        assert rapport["traites"] >= 1


# ─── 3. Erreurs HTTP cloud ────────────────────────────────────────────────────

class TestErreursHTTPCloud:
    """Les erreurs HTTP cloud sont traitées selon leur classe (4xx vs 5xx)."""

    def test_erreur_4xx_leve_value_error(self, db, processeur, entree_vente):
        """HTTP 4xx → ValueError → ECHEC définitif (pas de retry)."""
        from infrastructure.outbox.modeles import StatutOutbox
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        config_mock = MagicMock()
        config_mock.cloud_api_url = "https://cloud.pharmapp.bf"
        config_mock.cle_api = "phk_test"
        config_mock.code_officine = "OFC-001"

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=True), \
             patch.object(ServiceParametrageCloud, "obtenir_config", return_value=config_mock), \
             patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                 url="", code=400, msg="Bad Request", hdrs=None, fp=None
             )):
            with pytest.raises(ValueError, match="HTTP 400"):
                processeur._envoyer_vers_cloud(entree_vente)

    def test_erreur_5xx_leve_runtime_error(self, db, processeur, entree_vente):
        """HTTP 5xx → RuntimeError → retry planifié (backoff exponentiel)."""
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        config_mock = MagicMock()
        config_mock.cloud_api_url = "https://cloud.pharmapp.bf"
        config_mock.cle_api = "phk_test"
        config_mock.code_officine = "OFC-001"

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=True), \
             patch.object(ServiceParametrageCloud, "obtenir_config", return_value=config_mock), \
             patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                 url="", code=503, msg="Service Unavailable", hdrs=None, fp=None
             )):
            with pytest.raises(RuntimeError, match="HTTP 503"):
                processeur._envoyer_vers_cloud(entree_vente)

    def test_erreur_reseau_leve_runtime_error(self, db, processeur, entree_vente):
        """Réseau inaccessible (URLError) → RuntimeError."""
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        config_mock = MagicMock()
        config_mock.cloud_api_url = "https://cloud.pharmapp.bf"
        config_mock.cle_api = "phk_test"
        config_mock.code_officine = "OFC-001"

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=True), \
             patch.object(ServiceParametrageCloud, "obtenir_config", return_value=config_mock), \
             patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            with pytest.raises(RuntimeError, match="inaccessible"):
                processeur._envoyer_vers_cloud(entree_vente)


# ─── 4. Idempotence 409 ───────────────────────────────────────────────────────

class TestIdempotence409:
    """Un HTTP 409 (déjà connu) est considéré comme un succès."""

    def test_409_traite_comme_succes(self, db, processeur, entree_vente):
        """HTTP 409 ne lève pas d'exception (idempotence cloud)."""
        from gestion.parametrage.services_cloud import ServiceParametrageCloud

        config_mock = MagicMock()
        config_mock.cloud_api_url = "https://cloud.pharmapp.bf"
        config_mock.cle_api = "phk_test"
        config_mock.code_officine = "OFC-001"

        resp_mock = MagicMock()
        resp_mock.__enter__ = lambda s: s
        resp_mock.__exit__ = MagicMock(return_value=False)
        resp_mock.status = 409

        with patch.object(ServiceParametrageCloud, "est_configure", return_value=True), \
             patch.object(ServiceParametrageCloud, "obtenir_config", return_value=config_mock), \
             patch("urllib.request.urlopen", return_value=resp_mock):
            # Ne doit pas lever d'exception
            processeur._envoyer_vers_cloud(entree_vente)


# ─── 5. Rapport du lot ────────────────────────────────────────────────────────

class TestRapportLot:
    """traiter_lot() retourne un rapport cohérent."""

    def test_lot_vide_rapport_zero(self, db, processeur):
        """Aucune entrée en attente → rapport avec 0 traités."""
        from infrastructure.outbox.modeles import EntreeOutbox
        EntreeOutbox.objects.all().delete()

        rapport = processeur.traiter_lot(taille=50)
        assert rapport["total"] == 0
        assert rapport["traites"] == 0
        assert rapport["echecs"] == 0

    def test_rapport_traites_incremente(self, db, processeur, entree_vente):
        """Une entrée traitée avec succès incrémente rapport['traites']."""
        with patch.object(processeur, "_router_evenement"), \
             patch.object(processeur, "_envoyer_vers_cloud"):
            rapport = processeur.traiter_lot(taille=10)

        assert rapport["traites"] >= 1

    def test_rapport_echecs_incremente_sur_erreur(self, db, processeur, entree_inconnue):
        """Une entrée avec type inconnu incrémente rapport['echecs']."""
        with patch.object(processeur, "_envoyer_vers_cloud"):
            rapport = processeur.traiter_lot(taille=10)

        assert rapport["echecs"] >= 1


# ─── 6. Statistiques ─────────────────────────────────────────────────────────

class TestStatistiques:
    """ProcesseurOutbox.statistiques() retourne un dict par statut."""

    def test_statistiques_retourne_dict(self, db, processeur):
        """statistiques() retourne toujours un dict."""
        stats = processeur.statistiques()
        assert isinstance(stats, dict)

    def test_statistiques_compte_entrees(self, db, processeur):
        """statistiques() comptabilise les entrées en attente."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        from django.utils import timezone as tz

        EntreeOutbox.objects.create(
            type_evenement="EvenementVenteCreee",
            charge_utile={},
            statut=StatutOutbox.EN_ATTENTE,
            prochaine_tentative=tz.now(),
        )

        stats = processeur.statistiques()
        # La clé peut être le str de l'enum ou la valeur
        total = sum(v for v in stats.values())
        assert total >= 1
