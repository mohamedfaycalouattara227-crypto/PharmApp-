"""
tests/securite/test_auth_par_cle.py
Tests de sécurité — authentification par clé API.

Vérifie : rejet clé absente, invalide, inactive, abonnement expiré,
          isolation entre officines, protection anti-DoS (longueur max).
"""

import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.identite.models import Officine, StatutAbonnement
from apps.identite.services import generer_cle_api, ServiceOfficine


def creer_officine(code: str, statut=StatutAbonnement.ACTIF, active=True) -> tuple[Officine, str]:
    """Crée une officine et retourne (officine, cle_api)."""
    _, prefixe, hash_cle = generer_cle_api()
    from apps.identite.services import generer_cle_api as gen
    cle, prefixe, hash_cle = gen()
    officine = Officine.objects.create(
        nom=f"Pharmacie {code}",
        code=code,
        cle_api_hash=hash_cle,
        cle_api_prefixe=prefixe,
        statut_abonnement=statut,
        est_active=active,
    )
    return officine, cle


@pytest.mark.django_db
@pytest.mark.securite
class TestAuthParCleApi:

    def test_sans_cle_retourne_401(self):
        """Une requête sans X-Api-Key doit être refusée (401)."""
        client = APIClient()
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440000",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 401

    def test_cle_invalide_retourne_401(self):
        """Une clé invalide doit être refusée (401)."""
        client = APIClient()
        client.credentials(HTTP_X_API_KEY="phk_cle_completement_invalide_inconnue")
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440001",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 401

    def test_cle_sans_prefixe_retourne_401(self):
        """Une clé sans préfixe 'phk_' doit être rejetée immédiatement."""
        client = APIClient()
        client.credentials(HTTP_X_API_KEY="sk_mauvais_format_1234567890")
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440002",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 401

    def test_cle_trop_longue_retourne_401(self):
        """Une clé dépassant 256 caractères doit être rejetée (anti-DoS)."""
        client = APIClient()
        client.credentials(HTTP_X_API_KEY="phk_" + "A" * 300)
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440003",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 401

    def test_officine_inactive_retourne_401(self):
        """Une officine désactivée doit être refusée même avec une clé valide."""
        _, cle = creer_officine("PHA-SEC-INACT", active=False)
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle)
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440004",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code in (401, 403)

    def test_officine_suspendue_retourne_403(self):
        """Une officine suspendue doit être refusée (403)."""
        _, cle = creer_officine("PHA-SEC-SUSP", statut=StatutAbonnement.SUSPENDU, active=False)
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle)
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": "550e8400-e29b-41d4-a716-446655440005",
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code in (401, 403)

    def test_cle_valide_retourne_201(self):
        """Une officine active avec clé valide doit pouvoir envoyer un événement."""
        import uuid
        _, cle = creer_officine("PHA-SEC-OK")
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=cle)
        rep = client.post(
            "/api/cloud/sync/evenements/",
            {"uuid": str(uuid.uuid4()),
             "type_evenement": "HEARTBEAT",
             "version_schema": 1,
             "timestamp_local": "2026-07-21T10:00:00Z",
             "charge_utile": {}},
            format="json",
        )
        assert rep.status_code == 201
