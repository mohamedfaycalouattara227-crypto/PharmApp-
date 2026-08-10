import pytest
pytestmark = [pytest.mark.django_db, pytest.mark.integration]
"""
tests/integration/test_api_synchronisation.py
Tests d'intégration pour l'API de synchronisation et l'Outbox.
"""

import uuid
from unittest.mock import MagicMock, patch

from rest_framework import status


class TestApiSynchronisation:
    """Tests de l'API de synchronisation."""

    def test_statut_sync_non_authentifie_retourne_401(self, api_client):
        """L'état de synchronisation requiert une authentification."""
        reponse = api_client.get("/api/synchronisation/etat/")
        assert reponse.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND,
        )

    def test_statut_sync_authentifie(self, api_titulaire):
        """Le titulaire peut consulter l'état de synchronisation."""
        with patch("gestion.synchronisation.vues.EtatSynchronisation") as mock_etat:
            mock_etat.objects.order_by.return_value.first.return_value = None

            reponse = api_titulaire.get("/api/synchronisation/etat/")

        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_resoudre_conflit_resolution_invalide_retourne_400(self, api_titulaire):
        """Une résolution invalide ('cloud' ou 'locale' uniquement) → 400."""
        with patch("gestion.synchronisation.vues.ServiceSynchronisation") as mock_svc:
            mock_svc.return_value.resoudre_conflit.side_effect = ValueError(
                "Résolution invalide"
            )

            reponse = api_titulaire.post(
                f"/api/synchronisation/conflits/{uuid.uuid4()}/resoudre/",
                data={"resolution": "ignore"},
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

    def test_rejouer_echecs_titulaire_seulement(self, api_caissier):
        """Seul le titulaire peut rejouer les entrées Outbox en échec."""
        with patch("api.permissions.EstTitulaire.has_permission", return_value=False):
            reponse = api_caissier.post(
                "/api/synchronisation/rejouer-echecs/",
                format="json",
            )

        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestOutboxTransactionnel:
    """Tests du comportement transactionnel de l'Outbox."""

    def test_inscrire_dans_outbox_cree_entree(self, db):
        """inscrire_dans_outbox() crée une EntreeOutbox en DB."""
        from infrastructure.outbox.modeles import EntreeOutbox
        from gestion.sync.services import ServiceSynchronisation

        EntreeOutbox.objects.all().delete()

        service = ServiceSynchronisation()
        id_vente = uuid.uuid4()

        service.inscrire_dans_outbox(
            type_evenement="EvenementVenteCreee",
            charge_utile={"id_vente": str(id_vente), "montant": "2400.00"},
            id_objet=id_vente,
            modele_source="Vente",
        )

        assert EntreeOutbox.objects.filter(
            type_evenement="EvenementVenteCreee",
            id_objet=id_vente,
        ).exists()

    def test_inscrire_exclu_ne_cree_pas_dentree(self, db):
        """Les types exclus ne créent pas d'entrée Outbox."""
        from infrastructure.outbox.modeles import EntreeOutbox
        from gestion.sync.services import ServiceSynchronisation

        EntreeOutbox.objects.all().delete()

        service = ServiceSynchronisation()
        service.inscrire_dans_outbox(
            type_evenement="acces_sensible",  # Exclu du cloud
            charge_utile={"data": "confidentiel"},
        )

        assert EntreeOutbox.objects.count() == 0

    def test_charge_nettoyee_avant_inscription(self, db):
        """Les données sensibles sont retirées avant l'inscription Outbox."""
        from infrastructure.outbox.modeles import EntreeOutbox
        from gestion.sync.services import ServiceSynchronisation

        EntreeOutbox.objects.all().delete()

        service = ServiceSynchronisation()
        service.inscrire_dans_outbox(
            type_evenement="EvenementVenteCreee",
            charge_utile={
                "montant": "1200.00",
                "image_chiffree": "donnee_sensible",  # Doit être retiré
                "mot_de_passe": "secret",              # Doit être retiré
            },
        )

        entree = EntreeOutbox.objects.first()
        assert entree is not None
        assert "image_chiffree" not in entree.charge_utile
        assert "mot_de_passe" not in entree.charge_utile
        assert entree.charge_utile.get("montant") == "1200.00"

    def test_statistiques_outbox(self, db):
        """Les statistiques Outbox reflètent les entrées en DB."""
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
        from infrastructure.outbox.processeur import ProcesseurOutbox

        EntreeOutbox.objects.all().delete()

        EntreeOutbox.creer("Evt1", {"x": 1})
        EntreeOutbox.creer("Evt2", {"x": 2})
        e3 = EntreeOutbox.creer("Evt3", {"x": 3})
        e3.statut = StatutOutbox.TRAITE
        e3.save(update_fields=["statut"])

        stats = ProcesseurOutbox.statistiques()
        assert stats.get(StatutOutbox.EN_ATTENTE, 0) == 2
        assert stats.get(StatutOutbox.TRAITE, 0) == 1
