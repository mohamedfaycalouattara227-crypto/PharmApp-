"""
api/version_vue.py — Endpoint public d'identification de la version déployée.

Contrat (ÉTAPE 00, tâche 04) : une pharmacie doit pouvoir indiquer au support,
en une capture d'écran ou un appel API, la version exacte qu'elle exécute.

    GET /api/v1/version/  ->  200 OK
    {
      "application": "pharmapp-serveur-local",
      "version": "1.0.0",
      "revision": "a1b2c3d4e5f6",
      "construit_le": "2026-08-04T00:00:00Z",
      "environnement": "production",
      "api": "v1"
    }

Cet endpoint est volontairement **non authentifié** : il ne divulgue aucune
donnée métier et doit rester joignable même lorsque l'authentification est en
panne (c'est précisément dans ce cas que le support en a besoin).
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from pharmapp.version import date_construction, revision_git, version_applicative


class VueVersion(APIView):
    """Retourne l'identité de build du serveur local."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = None

    def get(self, request: Request) -> Response:
        return Response(
            {
                "application": "pharmapp-serveur-local",
                "version": version_applicative(),
                "revision": revision_git(),
                "construit_le": date_construction(),
                "environnement": "production" if getattr(settings, "IS_PROD", False) else "developpement",
                "api": "v1",
            }
        )
