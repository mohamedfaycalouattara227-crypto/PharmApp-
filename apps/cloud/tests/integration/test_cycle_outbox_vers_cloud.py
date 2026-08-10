"""
tests/integration/test_cycle_outbox_vers_cloud.py
Tests d'intégration — cycle complet outbox local → ingestion cloud.

Simule exactement ce que fait processeur.py côté serveur local :
  1. Créer une officine (provisionnement admin)
  2. Envoyer un événement avec la clé API reçue
  3. Vérifier persistance, idempotence, isolation
"""

import uuid

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.identite.models import Officine
from apps.synchronisation.models import EvenementSync, StatutTraitement


def client_admin() -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.CLOUD_ADMIN_TOKEN}")
    return client


@pytest.mark.django_db
@pytest.mark.integration
class TestCycleOutboxVersCloud:

    def _provisionner_officine(self, code: str) -> str:
        """Provisonne une officine et retourne sa clé API."""
        admin = client_admin()
        rep = admin.post(
            "/api/cloud/officines/",
            {"nom": f"Officine {code}", "code": code},
            format="json",
        )
        assert rep.status_code == 201, f"Provisionnement échoué : {rep.json()}"
        return rep.json()["cle_api"]

    def _client_officine(self, cle_api: str) -> APIClient:
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle_api)
        return client

    def test_cycle_complet_vente(self):
        """
        Scénario complet :
        1. Admin provisionne PHA-001
        2. PHA-001 envoie une vente
        3. L'événement est persisté et traité
        """
        cle = self._provisionner_officine("PHA-CYCLE-01")
        client = self._client_officine(cle)
        event_uuid = str(uuid.uuid4())

        rep = client.post(
            "/api/cloud/sync/evenements/",
            {
                "uuid": event_uuid,
                "type_evenement": "VENTE_CREEE",
                "version_schema": 1,
                "timestamp_local": "2026-07-21T10:30:00Z",
                "charge_utile": {
                    "id": str(uuid.uuid4()),
                    "total": 12500,
                    "lignes": [
                        {"medicament_id": "med-001", "quantite": 2, "prix_unitaire": 6250}
                    ],
                    "caissier": "CAISSIER_01",
                },
            },
            format="json",
        )

        assert rep.status_code == 201
        data = rep.json()
        assert data["statut"] == "reçu"
        assert data["uuid"] == event_uuid

        # Vérifier persistance
        ev = EvenementSync.objects.get(uuid=event_uuid)
        assert ev.type_evenement == "VENTE_CREEE"
        assert ev.statut_traitement == StatutTraitement.TRAITE
        assert ev.charge_utile["total"] == 12500

    def test_idempotence_cycle_complet(self):
        """
        Scénario idempotence :
        1. Envoyer UUID-X → 201
        2. Renvoyer UUID-X (simulation retry outbox) → 409
        3. Un seul événement en base
        """
        cle = self._provisionner_officine("PHA-CYCLE-02")
        client = self._client_officine(cle)
        event_uuid = str(uuid.uuid4())

        payload = {
            "uuid": event_uuid,
            "type_evenement": "STOCK_AJUSTE",
            "version_schema": 1,
            "timestamp_local": "2026-07-21T11:00:00Z",
            "charge_utile": {"medicament_id": "med-002", "delta": -5},
        }

        rep1 = client.post("/api/cloud/sync/evenements/", payload, format="json")
        rep2 = client.post("/api/cloud/sync/evenements/", payload, format="json")

        assert rep1.status_code == 201
        assert rep2.status_code == 409
        assert rep2.json()["statut"] == "déjà_connu"

        # Un seul événement en base
        assert EvenementSync.objects.filter(uuid=event_uuid).count() == 1

    def test_isolation_deux_pharmacies(self):
        """
        Deux pharmacies envoient chacune un événement.
        Chaque événement est lié à la bonne pharmacie.
        """
        cle_a = self._provisionner_officine("PHA-CYCLE-A")
        cle_b = self._provisionner_officine("PHA-CYCLE-B")

        client_a = self._client_officine(cle_a)
        client_b = self._client_officine(cle_b)

        uuid_a = str(uuid.uuid4())
        uuid_b = str(uuid.uuid4())

        client_a.post(
            "/api/cloud/sync/evenements/",
            {"uuid": uuid_a, "type_evenement": "VENTE_CREEE", "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z", "charge_utile": {"pharmacie": "A"}},
            format="json",
        )
        client_b.post(
            "/api/cloud/sync/evenements/",
            {"uuid": uuid_b, "type_evenement": "VENTE_CREEE", "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z", "charge_utile": {"pharmacie": "B"}},
            format="json",
        )

        ev_a = EvenementSync.objects.get(uuid=uuid_a)
        ev_b = EvenementSync.objects.get(uuid=uuid_b)

        officine_a = Officine.objects.get(code="PHA-CYCLE-A")
        officine_b = Officine.objects.get(code="PHA-CYCLE-B")

        assert ev_a.officine_id == officine_a.id
        assert ev_b.officine_id == officine_b.id
        assert ev_a.officine_id != ev_b.officine_id

    def test_rotation_cle_invalide_ancienne(self):
        """
        Après rotation de clé, l'ancienne clé doit être refusée.
        """
        # Provisionner
        ancienne_cle = self._provisionner_officine("PHA-CYCLE-ROT")
        officine = Officine.objects.get(code="PHA-CYCLE-ROT")

        # Vérifier que l'ancienne clé fonctionne
        client_ancien = self._client_officine(ancienne_cle)
        rep = client_ancien.post(
            "/api/cloud/sync/evenements/",
            {"uuid": str(uuid.uuid4()), "type_evenement": "HEARTBEAT",
             "version_schema": 1, "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 201

        # Rotation de clé (admin)
        admin = client_admin()
        rep_rot = admin.post(f"/api/cloud/officines/{officine.id}/regenerer-cle/")
        assert rep_rot.status_code == 200
        nouvelle_cle = rep_rot.json()["cle_api"]

        # L'ancienne clé doit être refusée
        rep_ancien = client_ancien.post(
            "/api/cloud/sync/evenements/",
            {"uuid": str(uuid.uuid4()), "type_evenement": "HEARTBEAT",
             "version_schema": 1, "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep_ancien.status_code == 401

        # La nouvelle clé doit fonctionner
        client_nouveau = self._client_officine(nouvelle_cle)
        rep_nouveau = client_nouveau.post(
            "/api/cloud/sync/evenements/",
            {"uuid": str(uuid.uuid4()), "type_evenement": "HEARTBEAT",
             "version_schema": 1, "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep_nouveau.status_code == 201

    def test_healthz_accessible_sans_auth(self):
        """Le liveness probe doit répondre sans authentification."""
        client = APIClient()
        rep = client.get("/api/cloud/healthz/")
        assert rep.status_code == 200
        assert rep.json()["statut"] == "ok"

    def test_readyz_accessible_sans_auth(self):
        """Le readiness probe doit répondre sans authentification."""
        client = APIClient()
        rep = client.get("/api/cloud/readyz/")
        assert rep.status_code == 200
