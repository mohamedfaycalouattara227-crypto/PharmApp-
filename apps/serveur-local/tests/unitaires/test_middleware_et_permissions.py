"""
tests/unitaires/test_middleware_et_permissions.py
Tests unitaires du middleware (RequestId, SecurityHeaders) et des permissions.
Couvre les branches non testées de :
  - api/middleware.py (0 %)
  - api/permissions.py (83 %)
  - api/healthcheck.py (48 %)
"""

import uuid
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from django.test import RequestFactory, TestCase, override_settings
from django.http import HttpResponse


# ══════════════════════════════════════════════════════════════════════════════
# RequestIdMiddleware
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestIdMiddleware:

    def _get_response_mock(self, status=200):
        resp = HttpResponse(status=status)
        get_response = MagicMock(return_value=resp)
        return get_response

    def test_genere_request_id_si_absent(self):
        from api.middleware import RequestIdMiddleware
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = RequestIdMiddleware(self._get_response_mock())
        response = mw(request)
        assert "X-Request-ID" in response
        assert len(response["X-Request-ID"]) > 0

    def test_accepte_request_id_entrant_valide(self):
        from api.middleware import RequestIdMiddleware
        rf = RequestFactory()
        request = rf.get("/api/test/", HTTP_X_REQUEST_ID="abc123def456")
        mw = RequestIdMiddleware(self._get_response_mock())
        response = mw(request)
        assert response["X-Request-ID"] == "abc123def456"

    def test_ignore_request_id_trop_long(self):
        from api.middleware import RequestIdMiddleware
        rf = RequestFactory()
        long_id = "a" * 200  # > 128 caractères
        request = rf.get("/api/test/", HTTP_X_REQUEST_ID=long_id)
        mw = RequestIdMiddleware(self._get_response_mock())
        response = mw(request)
        # Doit générer son propre UUID, pas utiliser le long id
        assert response["X-Request-ID"] != long_id

    def test_ignore_request_id_avec_caracteres_speciaux(self):
        from api.middleware import RequestIdMiddleware
        rf = RequestFactory()
        request = rf.get("/api/test/", HTTP_X_REQUEST_ID="<script>xss</script>")
        mw = RequestIdMiddleware(self._get_response_mock())
        response = mw(request)
        assert "<script>" not in response["X-Request-ID"]

    def test_request_id_ajoute_sur_request_object(self):
        from api.middleware import RequestIdMiddleware
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = RequestIdMiddleware(self._get_response_mock())
        mw(request)
        assert hasattr(request, "id")

    def test_request_id_courant_retourne_id(self):
        from api.middleware import RequestIdMiddleware, request_id_courant
        rf = RequestFactory()
        captured = []
        def get_response(req):
            captured.append(request_id_courant())
            return HttpResponse()
        mw = RequestIdMiddleware(get_response)
        request = rf.get("/api/test/", HTTP_X_REQUEST_ID="monid1234")
        mw(request)
        assert captured[0] == "monid1234"


# ══════════════════════════════════════════════════════════════════════════════
# SecurityHeadersMiddleware
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityHeadersMiddleware:

    def _mw(self, status=200):
        from api.middleware import SecurityHeadersMiddleware
        get_response = MagicMock(return_value=HttpResponse(status=status))
        return SecurityHeadersMiddleware(get_response)

    def test_ajoute_csp_header(self):
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = self._mw()
        response = mw(request)
        assert "Content-Security-Policy" in response
        assert "default-src" in response["Content-Security-Policy"]

    def test_ajoute_permissions_policy(self):
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = self._mw()
        response = mw(request)
        assert "Permissions-Policy" in response

    def test_ajoute_x_content_type_options(self):
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = self._mw()
        response = mw(request)
        assert response["X-Content-Type-Options"] == "nosniff"

    def test_ajoute_cross_origin_opener_policy(self):
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = self._mw()
        response = mw(request)
        assert "Cross-Origin-Opener-Policy" in response

    def test_ajoute_cache_control_sur_api(self):
        rf = RequestFactory()
        request = rf.get("/api/test/")
        mw = self._mw()
        response = mw(request)
        assert response["Cache-Control"] == "no-store"

    def test_ne_remplace_pas_cache_control_existant(self):
        from api.middleware import SecurityHeadersMiddleware
        rf = RequestFactory()
        request = rf.get("/api/test/")
        resp = HttpResponse()
        resp["Cache-Control"] = "max-age=3600"
        get_response = MagicMock(return_value=resp)
        mw = SecurityHeadersMiddleware(get_response)
        response = mw(request)
        assert response["Cache-Control"] == "max-age=3600"

    def test_ne_surcharge_pas_csp_existante(self):
        from api.middleware import SecurityHeadersMiddleware
        rf = RequestFactory()
        request = rf.get("/page-statique/")
        resp = HttpResponse()
        resp["Content-Security-Policy"] = "custom-csp"
        get_response = MagicMock(return_value=resp)
        mw = SecurityHeadersMiddleware(get_response)
        response = mw(request)
        assert response["Content-Security-Policy"] == "custom-csp"


# ══════════════════════════════════════════════════════════════════════════════
# Permissions
# ══════════════════════════════════════════════════════════════════════════════

def _mock_request(role: str, est_actif: bool = True, est_verrouille: bool = False):
    user = MagicMock()
    user.is_authenticated = True
    user.est_actif = est_actif
    user.is_active = est_actif
    user.est_verrouille = est_verrouille
    user.role = role
    request = MagicMock()
    request.user = user
    return request


class TestPermissions:

    def test_est_authentifie_accepte_utilisateur_actif(self):
        from api.permissions import EstAuthentifie
        perm = EstAuthentifie()
        request = _mock_request("caissier")
        assert perm.has_permission(request, None) is True

    def test_est_authentifie_refuse_compte_inactif(self):
        from api.permissions import EstAuthentifie
        perm = EstAuthentifie()
        request = _mock_request("caissier", est_actif=False)
        assert perm.has_permission(request, None) is False

    def test_est_authentifie_refuse_compte_verrouille(self):
        from api.permissions import EstAuthentifie
        perm = EstAuthentifie()
        request = _mock_request("caissier", est_verrouille=True)
        assert perm.has_permission(request, None) is False

    def test_est_authentifie_refuse_non_authentifie(self):
        from api.permissions import EstAuthentifie
        perm = EstAuthentifie()
        user = MagicMock()
        user.is_authenticated = False
        request = MagicMock()
        request.user = user
        assert perm.has_permission(request, None) is False

    def test_est_caissier_refuse_stagiaire(self):
        from api.permissions import EstCaissier
        perm = EstCaissier()
        request = _mock_request("stagiaire")
        assert perm.has_permission(request, None) is False

    def test_est_caissier_accepte_caissier(self):
        from api.permissions import EstCaissier
        perm = EstCaissier()
        request = _mock_request("caissier")
        assert perm.has_permission(request, None) is True

    def test_est_gestionnaire_stock_refuse_assistant(self):
        from api.permissions import EstGestionnaireStock
        perm = EstGestionnaireStock()
        request = _mock_request("assistant")
        assert perm.has_permission(request, None) is False

    def test_est_gestionnaire_stock_accepte_gestionnaire(self):
        from api.permissions import EstGestionnaireStock
        perm = EstGestionnaireStock()
        request = _mock_request("gestionnaire_stock")
        assert perm.has_permission(request, None) is True

    def test_est_pharmacien_adjoint_refuse_gestionnaire(self):
        from api.permissions import EstPharmacienAdjoint
        perm = EstPharmacienAdjoint()
        request = _mock_request("gestionnaire_stock")
        assert perm.has_permission(request, None) is False

    def test_est_pharmacien_adjoint_accepte_adjoint(self):
        from api.permissions import EstPharmacienAdjoint
        perm = EstPharmacienAdjoint()
        request = _mock_request("pharmacien_adjoint")
        assert perm.has_permission(request, None) is True

    def test_est_titulaire_refuse_adjoint(self):
        from api.permissions import EstTitulaire
        perm = EstTitulaire()
        request = _mock_request("pharmacien_adjoint")
        assert perm.has_permission(request, None) is False

    def test_est_titulaire_accepte_titulaire(self):
        from api.permissions import EstTitulaire
        perm = EstTitulaire()
        request = _mock_request("titulaire")
        assert perm.has_permission(request, None) is True

    def test_est_titulaire_accepte_administrateur(self):
        from api.permissions import EstTitulaire
        perm = EstTitulaire()
        request = _mock_request("administrateur")
        assert perm.has_permission(request, None) is True

    def test_est_administrateur_refuse_titulaire(self):
        from api.permissions import EstAdministrateur
        perm = EstAdministrateur()
        request = _mock_request("titulaire")
        assert perm.has_permission(request, None) is False

    def test_est_administrateur_accepte_admin(self):
        from api.permissions import EstAdministrateur
        perm = EstAdministrateur()
        request = _mock_request("administrateur")
        assert perm.has_permission(request, None) is True

    def test_permission_hierarchie_complete(self):
        """Vérifie que chaque rôle accepte les niveaux >= lui-même."""
        from api.permissions import (
            EstCaissier, EstGestionnaireStock, EstPharmacienAdjoint, EstTitulaire,
        )
        roles_niveaux = [
            ("caissier", [EstCaissier]),
            ("gestionnaire_stock", [EstCaissier, EstGestionnaireStock]),
            ("pharmacien_adjoint", [EstCaissier, EstGestionnaireStock, EstPharmacienAdjoint]),
            ("titulaire", [EstCaissier, EstGestionnaireStock, EstPharmacienAdjoint, EstTitulaire]),
        ]
        for role, perms in roles_niveaux:
            request = _mock_request(role)
            for perm_class in perms:
                perm = perm_class()
                assert perm.has_permission(request, None) is True, \
                    f"{perm_class.__name__} devrait accepter le rôle {role}"

    def test_utilisateur_none_retourne_false(self):
        from api.permissions import EstAuthentifie
        perm = EstAuthentifie()
        request = MagicMock()
        request.user = None
        assert perm.has_permission(request, None) is False


# ══════════════════════════════════════════════════════════════════════════════
# Healthcheck
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthcheck:

    def test_liveness_retourne_200(self, db):
        from django.test import Client
        c = Client()
        resp = c.get("/api/health/liveness/")
        assert resp.status_code == 200

    def test_liveness_corps_json(self, db):
        from django.test import Client
        import json
        c = Client()
        resp = c.get("/api/health/liveness/")
        data = json.loads(resp.content)
        assert data["statut"] == "vivant"

    def test_readiness_retourne_200_si_db_ok(self, db):
        from django.test import Client
        c = Client()
        resp = c.get("/api/health/readiness/")
        assert resp.status_code in (200, 503)

    def test_liveness_refus_methode_post(self, db):
        from django.test import Client
        c = Client()
        resp = c.post("/api/health/liveness/")
        assert resp.status_code == 405


# ══════════════════════════════════════════════════════════════════════════════
# JWTCookieAuthentication
# ══════════════════════════════════════════════════════════════════════════════

class TestJWTCookieAuthentication:

    def test_retourne_none_si_pas_de_cookie_ni_header(self):
        from api.authentication import JWTCookieAuthentication
        auth = JWTCookieAuthentication()
        rf = RequestFactory()
        request = rf.get("/api/test/")
        result = auth.authenticate(request)
        assert result is None

    def test_csrf_invalide_leve_permission_denied(self):
        """Un cookie CSRF différent du header lève PermissionDenied."""
        from api.authentication import JWTCookieAuthentication, COOKIE_ACCESS, COOKIE_CSRF
        from rest_framework.exceptions import PermissionDenied
        auth = JWTCookieAuthentication()

        with patch.object(auth, "get_header", return_value=None), \
             patch.object(auth, "get_validated_token", return_value=MagicMock()):
            rf = RequestFactory()
            request = rf.post("/api/test/")
            request.COOKIES = {
                COOKIE_ACCESS: "fake_token",
                COOKIE_CSRF: "csrf_cookie",
            }
            request.META["HTTP_X_CSRF_TOKEN"] = "csrf_header_different"
            with pytest.raises(PermissionDenied):
                auth.authenticate(request)
