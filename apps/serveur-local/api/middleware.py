"""
api/middleware.py — Middlewares transverses.

- RequestIdMiddleware : identifiant unique par requête (traçabilité audit)
- SecurityHeadersMiddleware : entêtes CSP/Permissions-Policy/…
- RequestIdFilter : injecte l'ID dans les logs
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


def request_id_courant() -> str:
    return _REQUEST_ID.get()


class RequestIdMiddleware:
    """Attribue un `X-Request-ID` par requête (accepte l'entrant s'il est propre)."""

    HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE = "X-Request-ID"
    MAX_LEN = 128

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.HEADER, "")
        rid = incoming if incoming and len(incoming) <= self.MAX_LEN and incoming.replace("-", "").isalnum() else uuid.uuid4().hex
        token = _REQUEST_ID.set(rid)
        request.id = rid
        try:
            response = self.get_response(request)
            response[self.RESPONSE] = rid
            return response
        finally:
            _REQUEST_ID.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = _REQUEST_ID.get()
        return True


# ─── Security headers ─────────────────────────────────────────────────────────

_DEFAULT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_DEFAULT_PERMISSIONS = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=()"
)


class SecurityHeadersMiddleware:
    """Ajoute CSP, Permissions-Policy, COOP/COEP, Cross-Origin-Resource-Policy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", _DEFAULT_CSP)
        response.setdefault("Permissions-Policy", _DEFAULT_PERMISSIONS)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Cache-Control par défaut pour les endpoints JSON
        if request.path.startswith("/api/") and "Cache-Control" not in response:
            response["Cache-Control"] = "no-store"
        return response
