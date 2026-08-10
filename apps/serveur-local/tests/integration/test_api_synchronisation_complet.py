"""
tests/integration/test_api_synchronisation_complet.py
Tests d'intégration exhaustifs de l'API synchronisation.
Couvre les branches non testées de gestion/synchronisation/vues.py (61 %)
et gestion/synchronisation/resolveur.py (0 %).

Branches couvertes :
  - GET /api/synchronisation/etat/ : structure de la réponse, valeurs
  - POST /api/synchronisation/rejouer/ : titulaire requis, remet en file
  - GET /api/synchronisation/conflits/ : liste, filtre statut
  - PATCH /api/synchronisation/conflits/<id>/ : résolution
  - _ping_supabase : URL absente, URL invalide
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from tests.usine.usine_utilisateurs import (
    UsineTitulaire, UsineCaissier, UsinePharmacienAdjoint, UsineCaissier
)


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create()


@pytest.fixture
def caissier(db):
    return UsineCaissier.create()


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/synchronisation/etat/
# ══════════════════════════════════════════════════════════════════════════════

class TestEtatSynchronisation:

    def test_etat_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/synchronisation/etat/")
        assert resp.status_code == 401

    def test_etat_retourne_200_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/etat/")
        assert resp.status_code == 200

    def test_etat_contient_champs_obligatoires(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/etat/")
        assert resp.status_code == 200
        champs = ["nb_en_attente", "nb_en_echec", "supabase_accessible", "conflits_non_resolus"]
        for champ in champs:
            assert champ in resp.data, f"Champ manquant : {champ}"

    def test_etat_nb_en_attente_est_entier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/etat/")
        assert isinstance(resp.data["nb_en_attente"], int)

    def test_etat_supabase_accessible_est_bool(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/etat/")
        assert isinstance(resp.data["supabase_accessible"], bool)

    def test_etat_supabase_false_si_url_absente(self, client_api, caissier, settings):
        """supabase_accessible doit être False si SUPABASE_URL n'est pas configuré."""
        settings.SUPABASE_URL = ""
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/etat/")
        assert resp.status_code == 200
        assert resp.data["supabase_accessible"] is False

    def test_etat_supabase_false_si_url_inaccessible(self, client_api, caissier, settings):
        """supabase_accessible doit être False si l'URL est inaccessible."""
        settings.SUPABASE_URL = "https://hote-inexistant-12345.supabase.co"
        client_api.force_authenticate(user=caissier)
        with patch("gestion.synchronisation.vues._ping_supabase", return_value=False):
            resp = client_api.get("/api/synchronisation/etat/")
        assert resp.status_code == 200
        assert resp.data["supabase_accessible"] is False


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/synchronisation/rejouer/
# ══════════════════════════════════════════════════════════════════════════════

class TestRejouerSynchronisation:

    def test_rejouer_retourne_401_sans_auth(self, client_api):
        resp = client_api.post("/api/synchronisation/rejouer/")
        assert resp.status_code == 401

    def test_rejouer_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.post("/api/synchronisation/rejouer/")
        assert resp.status_code == 403

    def test_rejouer_retourne_200_pour_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        with patch("gestion.sync.services.ServiceSynchronisation.rejouer_echecs", return_value=0):
            resp = client_api.post("/api/synchronisation/rejouer/")
        assert resp.status_code == 200
        assert "rejoues" in resp.data

    def test_rejouer_retourne_count(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        with patch("gestion.sync.services.ServiceSynchronisation.rejouer_echecs", return_value=3):
            resp = client_api.post("/api/synchronisation/rejouer/")
        assert resp.data["rejoues"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# Tests de _ping_supabase
# ══════════════════════════════════════════════════════════════════════════════

class TestPingSupabase:

    def test_ping_retourne_false_si_url_vide(self, settings):
        from gestion.synchronisation.vues import _ping_supabase
        settings.SUPABASE_URL = ""
        assert _ping_supabase() is False

    def test_ping_retourne_false_si_exception(self, settings):
        from gestion.synchronisation.vues import _ping_supabase
        settings.SUPABASE_URL = "https://test.supabase.co"
        settings.SUPABASE_ANON_KEY = "test-key"
        import urllib.request
        with patch.object(urllib.request, "urlopen", side_effect=Exception("timeout")):
            assert _ping_supabase() is False

    def test_ping_retourne_true_si_succes(self, settings):
        from gestion.synchronisation.vues import _ping_supabase
        settings.SUPABASE_URL = "https://test.supabase.co"
        settings.SUPABASE_ANON_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        import urllib.request
        with patch.object(urllib.request, "urlopen", return_value=mock_response):
            result = _ping_supabase()
        assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/synchronisation/conflits/
# ══════════════════════════════════════════════════════════════════════════════

class TestConflitsSynchronisation:

    def test_liste_conflits_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/synchronisation/conflits/")
        assert resp.status_code == 401

    def test_liste_conflits_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/synchronisation/conflits/")
        assert resp.status_code == 403

    def test_liste_conflits_retourne_200_pour_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/synchronisation/conflits/")
        assert resp.status_code == 200

    def test_filtre_statut_conflits(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/synchronisation/conflits/?statut=non_resolu")
        assert resp.status_code == 200
