"""
api/authentication.py
Backends d'authentification pour le Cloud PharmApp.

Deux classes distinctes selon l'appelant :
  - AuthenticationParCleApi      : pharmacies (machine-à-machine)
  - AuthenticationParTokenAdmin  : administrateur PharmApp (humain)
"""

import hashlib
import logging
import secrets

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger("pharmapp_cloud.securite")


class AuthenticationParCleApi(BaseAuthentication):
    """
    Authentifie une pharmacie via son header X-Api-Key.

    Flux :
      1. Lit X-Api-Key depuis le header HTTP.
      2. Vérifie le format (préfixe "phk_") et la longueur max (DoS).
      3. Hache la clé candidate (SHA-256) et recherche le hash en base.
      4. En cas d'absence : exécute compare_digest factice (anti-timing).
      5. Vérifie que l'officine est active et son abonnement valide.
      6. Met à jour `derniere_connexion` et `version_logiciel` si fournie.

    Returns : (officine, "api_key") si valide, None si header absent.
    Raises  : AuthenticationFailed si header présent mais invalide.
    """

    HEADER_CLE     = "HTTP_X_API_KEY"
    HEADER_VERSION = "HTTP_X_PHARMAPP_VERSION"
    PREFIXE_VALIDE = "phk_"
    LONGUEUR_MAX   = 256

    # Hash factice précalculé pour les branches DoesNotExist (anti-timing).
    _HASH_FACTICE = hashlib.sha256(b"__pharmapp_dummy_key__").hexdigest()

    def authenticate(self, request):
        cle_candidate = request.META.get(self.HEADER_CLE, "")

        if not cle_candidate:
            return None  # pas de clé → passe au backend suivant

        # ── Validation format précoce ──────────────────────────────────────
        if len(cle_candidate) > self.LONGUEUR_MAX:
            raise AuthenticationFailed("Clé API invalide.")

        if not cle_candidate.startswith(self.PREFIXE_VALIDE):
            raise AuthenticationFailed("Clé API invalide.")

        # ── Résolution de l'officine ───────────────────────────────────────
        from apps.identite.models import Officine
        from apps.identite.services import _hacher_cle, ServiceOfficine

        hash_candidate = _hacher_cle(cle_candidate)

        try:
            officine = Officine.objects.get(cle_api_hash=hash_candidate)
        except Officine.DoesNotExist:
            # Temps constant : on exécute compare_digest même en cas d'absence.
            secrets.compare_digest(hash_candidate, self._HASH_FACTICE)
            logger.warning(
                "Tentative avec clé API inconnue",
                extra={"prefixe": cle_candidate[:8]},
            )
            raise AuthenticationFailed("Clé API invalide.")

        # ── Vérification statut ────────────────────────────────────────────
        if not officine.est_active:
            logger.warning(
                "Tentative depuis officine inactive",
                extra={"officine_id": str(officine.id), "code": officine.code},
            )
            raise AuthenticationFailed("Officine inactive.")

        if not officine.abonnement_actif:
            logger.warning(
                "Tentative depuis officine sans abonnement actif",
                extra={"officine_id": str(officine.id), "statut": officine.statut_abonnement},
            )
            raise AuthenticationFailed("Abonnement expiré ou suspendu.")

        # ── Mise à jour télémétrie ─────────────────────────────────────────
        version_logiciel = request.META.get(self.HEADER_VERSION, "")
        ServiceOfficine.mettre_a_jour_connexion(officine, version_logiciel or None)

        return (officine, "api_key")

    def authenticate_header(self, request) -> str:
        return 'ApiKey realm="PharmApp Cloud"'


class AuthenticationParTokenAdmin(BaseAuthentication):
    """
    Authentifie l'administrateur PharmApp via le header Authorization: Bearer <token>.

    Le token est comparé en temps constant contre CLOUD_ADMIN_TOKEN
    défini dans settings.py.

    Returns : ("admin", "admin") si valide, None si header absent.
    Raises  : AuthenticationFailed si Bearer présent mais token invalide.
    """

    def authenticate(self, request):
        from django.conf import settings

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token_candidate = auth_header[len("Bearer "):]

        if not secrets.compare_digest(
            token_candidate.encode("utf-8"),
            settings.CLOUD_ADMIN_TOKEN.encode("utf-8"),
        ):
            logger.warning("Tentative d'accès admin avec token invalide")
            raise AuthenticationFailed("Token administrateur invalide.")

        return ("admin", "admin")

    def authenticate_header(self, request) -> str:
        return 'Bearer realm="PharmApp Cloud Admin"'
