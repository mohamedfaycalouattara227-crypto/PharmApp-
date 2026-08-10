"""
tests/securite/test_provisionnement_admin.py
Tests de sécurité — accès admin exclusif au provisionnement.

Vérifie que seul l'admin peut créer des officines,
qu'une officine ne peut pas s'auto-provisionner,
et que la clé admin protège correctement l'endpoint.
"""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.identite.models import Officine
from apps.identite.services import generer_cle_api


def client_admin() -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {settings.CLOUD_ADMIN_TOKEN}")
    return client


def client_officine(code: str = "PHA-ADM-FIXTURE") -> APIClient:
    cle, prefixe, hash_cle = generer_cle_api()
    Officine.objects.get_or_create(
        code=code,
        defaults={
            "nom": "Fixture Officine",
            "cle_api_hash": hash_cle,
            "cle_api_prefixe": prefixe,
            "est_active": True,
        },
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=cle)
    return client


@pytest.mark.django_db
@pytest.mark.securite
class TestProvisionnementAdmin:

    def test_admin_peut_creer_officine(self):
        """L'admin peut créer une officine."""
        client = client_admin()
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Pharmacie Sécurité Test", "code": "PHA-SEC-NEW"},
            format="json",
        )
        assert rep.status_code == 201
        data = rep.json()
        assert "cle_api" in data
        assert data["cle_api"].startswith("phk_")
        assert "cle_api_hash" not in data  # jamais exposé

    def test_cle_api_presente_une_seule_fois(self):
        """La clé API complète ne doit apparaître qu'au moment de la création."""
        client = client_admin()
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Pharmacie Once Key", "code": "PHA-ONCE"},
            format="json",
        )
        assert rep.status_code == 201
        cle_creation = rep.json()["cle_api"]
        officine_id = rep.json()["officine_id"]

        # Récupération via GET — ne doit PAS exposer la clé
        rep_get = client.get(f"/api/cloud/officines/{officine_id}/")
        assert rep_get.status_code == 200
        data_get = rep_get.json()
        assert "cle_api" not in data_get
        assert "cle_api_hash" not in data_get

    def test_sans_token_retourne_401(self):
        """Sans token admin, l'endpoint de provisionnement retourne 401."""
        client = APIClient()
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Tentative non autorisée", "code": "PHA-UNAUTH"},
            format="json",
        )
        assert rep.status_code == 401

    def test_token_admin_invalide_retourne_401(self):
        """Un token admin incorrect retourne 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer mauvais_token_admin")
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Tentative avec mauvais token", "code": "PHA-BADTOK"},
            format="json",
        )
        assert rep.status_code == 401

    def test_officine_ne_peut_pas_provisionner(self):
        """
        Une officine authentifiée (clé API) ne doit pas pouvoir
        créer d'autres officines.
        """
        client = client_officine("PHA-ADM-SELF")
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Tentative d'auto-provisionnement", "code": "PHA-SELFPROV"},
            format="json",
        )
        # Doit retourner 401 ou 403, jamais 201
        assert rep.status_code in (401, 403)

    def test_code_duplique_retourne_409(self):
        """Créer deux officines avec le même code doit retourner 409."""
        client = client_admin()
        client.post(
            "/api/cloud/officines/",
            {"nom": "Officine Originale", "code": "PHA-DUP"},
            format="json",
        )
        rep = client.post(
            "/api/cloud/officines/",
            {"nom": "Tentative doublon", "code": "PHA-DUP"},
            format="json",
        )
        assert rep.status_code == 409

    def test_liste_officines_reservee_admin(self):
        """La liste des officines est réservée à l'admin."""
        client_anon = APIClient()
        assert client_anon.get("/api/cloud/officines/").status_code == 401

        client_off = client_officine("PHA-ADM-LIST")
        assert client_off.get("/api/cloud/officines/").status_code in (401, 403)

        assert client_admin().get("/api/cloud/officines/").status_code == 200
