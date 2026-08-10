"""api/version_vue.py — Identité de build du Cloud PharmApp (ÉTAPE 00, tâche 04)."""

from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from pharmapp_cloud.version import date_construction, revision_git, version_applicative


class VueVersion(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request: Request) -> Response:
        return Response(
            {
                "application": "pharmapp-cloud",
                "version": version_applicative(),
                "revision": revision_git(),
                "construit_le": date_construction(),
                "environnement": "production" if getattr(settings, "IS_PROD", False) else "developpement",
                "api": "v1",
            }
        )
