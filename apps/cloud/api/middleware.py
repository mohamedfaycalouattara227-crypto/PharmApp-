"""
api/middleware.py
Middleware de sécurité et de traçabilité pour le Cloud PharmApp.

  - RequestIdMiddleware     : injecte X-Request-ID sur chaque requête/réponse
  - SecurityHeadersMiddleware : CSP, Permissions-Policy, COOP, CORP, Referrer
"""

import threading
import uuid

_local = threading.local()


def get_request_id() -> str:
    """Retourne le Request-ID du thread courant (vide si hors contexte requête)."""
    return getattr(_local, "request_id", "")


class RequestIdMiddleware:
    """
    Injecte un identifiant unique par requête.

    - Lit X-Request-ID depuis le header entrant (pour chaînage de logs).
    - En génère un nouveau si absent.
    - L'expose sur request.request_id et le retourne dans la réponse.
    - Le stocke dans un thread-local pour les formateurs de log.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (
            request.META.get("HTTP_X_REQUEST_ID", "")
            or str(uuid.uuid4())
        )
        request.request_id = request_id
        _local.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id

        _local.request_id = ""
        return response


class SecurityHeadersMiddleware:
    """
    Injecte les en-têtes de sécurité HTTP sur toutes les réponses API.

    Politique volontairement stricte : le Cloud PharmApp est une API machine-à-machine
    (Phase 1), pas une application web avec navigation. Les headers reflètent cela.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._appliquer_headers(response)
        return response

    def _appliquer_headers(self, response) -> None:
        # Interdire le framing (clickjacking — défense en profondeur)
        response["X-Frame-Options"] = "DENY"

        # Empêcher le MIME sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Politique de référent stricte
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Isolation des origines croisées
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response["Cross-Origin-Resource-Policy"] = "same-origin"

        # Désactiver tous les capteurs et périphériques (API est headless)
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), bluetooth=()"
        )

        # CSP restrictive — API pure JSON, aucun contenu HTML dynamique
        response["Content-Security-Policy"] = (
            "default-src 'none'; "
            "frame-ancestors 'none'"
        )

        # Pas de cache sur les réponses API (données sensibles)
        if "/api/" in response.get("Content-Type", "") or True:
            response["Cache-Control"] = "no-store, max-age=0"
            response["Pragma"] = "no-cache"
