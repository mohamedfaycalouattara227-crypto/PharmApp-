"""
api/authentication.py

Authentification JWT via cookie httpOnly, complétée par un token CSRF
double-cookie (§Sécurité, remplacement de sessionStorage).

Modèle :
- ``pharmapp_access``  : httpOnly, SameSite=Strict, Secure en prod.
- ``pharmapp_refresh`` : httpOnly, SameSite=Strict, Secure en prod, path=/api/auth/.
- ``pharmapp_csrf``    : lisible JS, doit être renvoyé en header
  ``X-CSRF-Token`` sur toute requête non idempotente (POST/PUT/PATCH/DELETE).

Rationale :
- Le token n'est plus accessible en JavaScript → immune aux vols par XSS.
- La CSRF est mitigée par la comparaison cookie ↔ header (double-submit) :
  un site tiers ne peut pas lire ``pharmapp_csrf`` (Same-Origin Policy), donc
  ne peut pas fabriquer le header correspondant.
"""
from __future__ import annotations

import hmac

from django.conf import settings
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

COOKIE_ACCESS = "pharmapp_access"
COOKIE_REFRESH = "pharmapp_refresh"
COOKIE_CSRF = "pharmapp_csrf"
HEADER_CSRF = "HTTP_X_CSRF_TOKEN"

_METHODES_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class JWTCookieAuthentication(JWTAuthentication):
    """Lit le JWT dans le cookie httpOnly et applique le double-submit CSRF."""

    def authenticate(self, request):
        header_token = self.get_header(request)
        raw_token = None
        if header_token is not None:
            # Compat : header Authorization: Bearer <t> (mobile, tests).
            raw_token = self.get_raw_token(header_token)
        else:
            cookie_token = request.COOKIES.get(COOKIE_ACCESS)
            if not cookie_token:
                return None
            raw_token = cookie_token.encode("ascii", errors="ignore")

        validated_token = self.get_validated_token(raw_token)

        # Double-submit CSRF pour toute méthode non idempotente lorsqu'on est
        # authentifié par cookie (pas par header — l'appel via header ne
        # provient jamais d'un contexte navigateur cross-site).
        if header_token is None and request.method in _METHODES_UNSAFE:
            cookie_csrf = request.COOKIES.get(COOKIE_CSRF, "")
            header_csrf = request.META.get(HEADER_CSRF, "")
            if not cookie_csrf or not header_csrf or not hmac.compare_digest(cookie_csrf, header_csrf):
                raise exceptions.PermissionDenied("Jeton CSRF manquant ou invalide.")

        return self.get_user(validated_token), validated_token


def poser_cookies_session(response, access: str, refresh: str, csrf: str) -> None:
    """Applique les 3 cookies avec les bons flags selon l'environnement."""
    is_prod = not settings.DEBUG
    duree_access = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    duree_refresh = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    commun = {"secure": is_prod, "samesite": "Strict", "path": "/"}
    response.set_cookie(COOKIE_ACCESS, access, max_age=duree_access, httponly=True, **commun)
    response.set_cookie(
        COOKIE_REFRESH, refresh, max_age=duree_refresh, httponly=True,
        secure=is_prod, samesite="Strict", path="/api/auth/",
    )
    # CSRF lisible JS mais non exportable cross-origin (Same-Origin Policy).
    response.set_cookie(
        COOKIE_CSRF, csrf, max_age=duree_access, httponly=False,
        secure=is_prod, samesite="Strict", path="/",
    )


def effacer_cookies_session(response) -> None:
    response.delete_cookie(COOKIE_ACCESS, path="/")
    response.delete_cookie(COOKIE_REFRESH, path="/api/auth/")
    response.delete_cookie(COOKIE_CSRF, path="/")
