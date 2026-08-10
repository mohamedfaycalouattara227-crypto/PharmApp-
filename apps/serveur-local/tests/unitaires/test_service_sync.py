"""
tests/unitaires/test_service_sync.py
Tests unitaires du service de synchronisation (gestion/sync/services.py).
Couverture cible : 100 % du service de synchronisation.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unitaire


class TestServiceSynchronisation:
    """Tests du service de synchronisation locale ↔ cloud."""

    @pytest.fixture
    def service(self):
        from gestion.sync.services import ServiceSynchronisation
        return ServiceSynchronisation()

    # ─── Tests d'obtenir_statut ───────────────────────────────────────────────

    def test_obtenir_statut_retourne_statut_sync(self, service, db):
        """obtenir_statut() retourne un StatutSync avec les métriques actuelles."""
        from gestion.sync.services import StatutSync

        with patch("gestion.sync.services.EntreeOutbox") as mock_outbox:
            mock_outbox.objects.filter.return_value.count.return_value = 5
            mock_outbox.objects.filter.return_value.count.side_effect = [5, 2]

            # Simuler pas d'EtatSynchronisation en DB
            with patch("gestion.sync.services.EtatSynchronisation") as mock_etat:
                mock_etat.objects.order_by.return_value.first.return_value = None
                with patch("gestion.sync.services.ConflitSynchronisation") as mock_conflit:
                    mock_conflit.objects.filter.return_value.count.return_value = 1
                    statut = service.obtenir_statut()

        assert isinstance(statut, StatutSync)

    # ─── Tests de nettoyer_charge ─────────────────────────────────────────────

    def test_nettoyer_charge_supprime_image_chiffree(self, service):
        """_nettoyer_charge() supprime les données d'image d'ordonnance."""
        charge = {
            "id_vente": str(uuid.uuid4()),
            "montant": "2400.00",
            "image_chiffree": "base64blabla",
            "vecteur_initialisation": "iv_secret",
        }
        nettoyee = service._nettoyer_charge(charge)

        assert "image_chiffree" not in nettoyee
        assert "vecteur_initialisation" not in nettoyee
        assert "id_vente" in nettoyee
        assert "montant" in nettoyee

    def test_nettoyer_charge_supprime_mots_de_passe(self, service):
        """_nettoyer_charge() supprime les mots de passe et secrets."""
        charge = {
            "email": "user@test.bf",
            "mot_de_passe": "secret123",
            "token": "jwt_token_sensible",
            "secret": "valeur_secrete",
        }
        nettoyee = service._nettoyer_charge(charge)

        assert "mot_de_passe" not in nettoyee
        assert "token" not in nettoyee
        assert "secret" not in nettoyee
        assert "email" in nettoyee

    def test_nettoyer_charge_supprime_empreinte_sha256(self, service):
        """_nettoyer_charge() supprime les empreintes cryptographiques internes."""
        charge = {
            "type": "audit",
            "empreinte_sha256": "hash_confidentiel",
        }
        nettoyee = service._nettoyer_charge(charge)

        assert "empreinte_sha256" not in nettoyee

    def test_nettoyer_charge_charge_vide(self, service):
        """_nettoyer_charge() gère une charge vide sans erreur."""
        assert service._nettoyer_charge({}) == {}

    def test_nettoyer_charge_aucun_champ_sensible(self, service):
        """_nettoyer_charge() ne modifie pas une charge sans données sensibles."""
        charge = {"id": "abc", "statut": "validee", "montant": "1000"}
        nettoyee = service._nettoyer_charge(charge)
        assert nettoyee == charge

    # ─── Tests de inscrire_dans_outbox ────────────────────────────────────────

    def test_inscrire_exclu_type_exclus_cloud(self, service):
        """Les événements dans TYPES_EXCLUS_CLOUD ne sont pas inscrits."""
        with patch("gestion.sync.services.EntreeOutbox") as mock:
            result = service.inscrire_dans_outbox(
                type_evenement="acces_sensible",  # Dans TYPES_EXCLUS_CLOUD
                charge_utile={"data": "sensible"},
            )

        mock.creer.assert_not_called()
        assert result is None

    def test_inscrire_dans_outbox_appelle_creer(self, service, db):
        """inscrire_dans_outbox() crée une EntreeOutbox avec les données nettoyées."""
        with patch("gestion.sync.services.EntreeOutbox") as mock_outbox:
            mock_outbox.creer.return_value = MagicMock(id=uuid.uuid4())

            service.inscrire_dans_outbox(
                type_evenement="EvenementVenteCreee",
                charge_utile={"montant": "1200.00"},
                id_objet=uuid.uuid4(),
                modele_source="Vente",
            )

        mock_outbox.creer.assert_called_once()
        kwargs = mock_outbox.creer.call_args[1]
        assert kwargs["type_evenement"] == "EvenementVenteCreee"
        assert "montant" in kwargs["charge_utile"]

    # ─── Tests de detecter_conflits ───────────────────────────────────────────

    def test_detecter_conflits_donnees_identiques_retourne_none(self, service):
        """Pas de conflit si les données locales et cloud sont identiques."""
        donnees = {"stock": 50, "prix": "800.00"}
        result = service.detecter_conflits(
            modele="Lot",
            id_objet=uuid.uuid4(),
            donnees_locales=donnees,
            donnees_cloud=donnees,
        )
        assert result is None

    def test_detecter_conflits_donnees_differentes_cree_conflit(self, service, db):
        """Un conflit est créé si les données locales et cloud divergent."""
        with patch("gestion.sync.services.ConflitSynchronisation") as mock_conflit:
            conflit_mock = MagicMock()
            mock_conflit.objects.get_or_create.return_value = (conflit_mock, True)

            result = service.detecter_conflits(
                modele="Lot",
                id_objet=uuid.uuid4(),
                donnees_locales={"stock": 50},
                donnees_cloud={"stock": 45},  # Différent !
            )

        mock_conflit.objects.get_or_create.assert_called_once()
        assert result is conflit_mock

    # ─── Tests de rejouer_echecs ──────────────────────────────────────────────

    def test_rejouer_echecs_retourne_zero_si_aucun_echec(self, service, db):
        """rejouer_echecs() retourne 0 si aucune entrée en ECHEC."""
        with patch("gestion.sync.services.EntreeOutbox") as mock:
            mock.objects.filter.return_value.__getitem__ = MagicMock(return_value=[])
            # Simuler aucune entrée en échec
            from infrastructure.outbox.modeles import StatutOutbox
            from unittest.mock import MagicMock as MM

            class FakeMockFilter:
                def __getitem__(self, s): return []
                def __iter__(self): return iter([])

            mock.objects.filter.return_value = FakeMockFilter()
            count = service.rejouer_echecs()

        assert count == 0

    # ─── Tests des types exclus ───────────────────────────────────────────────

    def test_types_exclus_cloud_contient_image_ordonnance(self, service):
        """Les images d'ordonnances font partie des types exclus du cloud."""
        assert "image_ordonnance" in service.TYPES_EXCLUS_CLOUD

    def test_types_exclus_cloud_contient_acces_sensible(self, service):
        """Les accès sensibles (audit) sont exclus du cloud."""
        assert "acces_sensible" in service.TYPES_EXCLUS_CLOUD

    def test_types_exclus_cloud_est_un_frozenset(self, service):
        """TYPES_EXCLUS_CLOUD est un frozenset immuable."""
        assert isinstance(service.TYPES_EXCLUS_CLOUD, frozenset)

    # ─── Tests de traiter_outbox ──────────────────────────────────────────────

    def test_traiter_outbox_retourne_resultat_synchronisation(self, service):
        """traiter_outbox() retourne un ResultatSynchronisation."""
        from gestion.sync.services import ResultatSynchronisation

        with patch("gestion.sync.services.ProcesseurOutbox") as mock_proc:
            mock_proc.return_value.traiter_lot.return_value = {
                "traites": 10,
                "echecs": 0,
                "total": 10,
            }
            resultat = service.traiter_outbox()

        assert isinstance(resultat, ResultatSynchronisation)
        assert resultat.succes is True
        assert resultat.evenements_envoyes == 10

    def test_traiter_outbox_erreur_retourne_echec(self, service):
        """traiter_outbox() capture les exceptions et retourne un résultat en échec."""
        from gestion.sync.services import ResultatSynchronisation

        with patch("gestion.sync.services.ProcesseurOutbox") as mock_proc:
            mock_proc.return_value.traiter_lot.side_effect = RuntimeError("Erreur Celery")
            resultat = service.traiter_outbox()

        assert isinstance(resultat, ResultatSynchronisation)
        assert resultat.succes is False
        assert "Erreur Celery" in resultat.erreur
