"""
tests/securite/test_isolation_officines.py
Tests de sécurité — isolation stricte entre officines.

Vérifie qu'une officine ne peut pas lire ni écrire les données d'une autre.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from apps.identite.models import Officine, StatutAbonnement
from apps.identite.services import generer_cle_api
from apps.synchronisation.models import EvenementSync
from apps.synchronisation.services import DonneesEvenement, ServiceIngestion
from django.utils import timezone


def creer_officine(code: str) -> tuple[Officine, str]:
    cle, prefixe, hash_cle = generer_cle_api()
    officine = Officine.objects.create(
        nom=f"Pharmacie {code}",
        code=code,
        cle_api_hash=hash_cle,
        cle_api_prefixe=prefixe,
        statut_abonnement=StatutAbonnement.ACTIF,
        est_active=True,
    )
    return officine, cle


@pytest.mark.django_db
@pytest.mark.securite
class TestIsolationOfficines:

    def test_cle_officine_a_ne_donne_pas_acces_officine_b(self):
        """
        La clé API de l'officine A ne doit jamais permettre d'agir
        au nom de l'officine B.
        """
        officine_a, cle_a = creer_officine("PHA-ISO-A")
        officine_b, cle_b = creer_officine("PHA-ISO-B")

        # On envoie un événement avec la clé de A
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle_a)
        event_uuid = str(uuid.uuid4())
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": event_uuid,
             "type_evenement": "VENTE_CREEE",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {"total": 5000}},
            format="json",
        )
        assert rep.status_code == 201

        # L'événement doit être lié à A, pas à B
        ev = EvenementSync.objects.get(uuid=event_uuid)
        assert ev.officine_id == officine_a.id
        assert ev.officine_id != officine_b.id

    def test_les_evenements_dune_officine_sont_isoles(self):
        """
        Les événements de l'officine A ne doivent pas être visibles
        par une requête de l'officine B.
        """
        officine_a, cle_a = creer_officine("PHA-ISO-C")
        officine_b, cle_b = creer_officine("PHA-ISO-D")

        # Créer un événement pour A
        donnees = DonneesEvenement(
            uuid=uuid.uuid4(),
            type_evenement="VENTE_CREEE",
            version_schema=1,
            timestamp_local=timezone.now(),
            charge_utile={"confidentiel": "donnees_pharmacie_A"},
        )
        ServiceIngestion.ingerer(officine_a, donnees)

        # Les événements de A ne sont pas accessibles via officine B
        evenements_b = EvenementSync.objects.filter(officine=officine_b)
        assert evenements_b.count() == 0

        # Les événements de A sont bien enregistrés sous A
        evenements_a = EvenementSync.objects.filter(officine=officine_a)
        assert evenements_a.count() == 1

    def test_cle_officine_a_ne_peut_pas_etre_construite_par_connaissance_du_code(self):
        """
        Le code d'une officine ("PHA-001") ne permet pas de déduire sa clé API.
        La clé doit être générée de manière aléatoire indépendamment du code.
        """
        officine_a, cle_a = creer_officine("PHA-ISO-E")

        # Tenter de forger une clé à partir du code
        cle_forgee = f"phk_{officine_a.code}"
        assert cle_forgee != cle_a

        # Vérifier que la clé forgée est rejetée
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle_forgee)
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": str(uuid.uuid4()),
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 401
