"""
pharmapp/urls.py — Routage principal.

Expose :
    /api/…            — API REST (alias de compatibilité)
    /api/v1/…         — API REST versionnée (même routage)
    /api/v1/version/  — identité de build (non authentifié, ÉTAPE 00)
    /healthz/         — liveness probe (Kubernetes / Docker)
    /readyz/          — readiness probe
    /admin/           — interface d'administration Django (protégée par IP/VPN)
"""

import os

from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from api.healthcheck import liveness, readiness
from api.version_vue import VueVersion

urlpatterns = [
    path("healthz/", liveness, name="liveness"),
    path("readyz/", readiness, name="readiness"),
    # Alias de compatibilité pour le contrat local historique.
    path("api/health/liveness/", liveness, name="api-health-liveness"),
    path("api/health/readiness/", readiness, name="api-health-readiness"),
    path("api/v1/version/", VueVersion.as_view(), name="version"),
    # L'API est exposée sous deux préfixes équivalents :
    #   /api/…     — compatibilité poste client historique (api-client.ts)
    #   /api/v1/…  — préfixe versionné (contrat documenté, tests sécurité)
    path("api/", include("api.urls")),
    path("api/v1/", include("api.urls")),
]

# L'admin Django reste actif en dev ; en prod, l'activer explicitement.
_admin_actif = (not getattr(settings, "IS_PROD", False)) or (
    os.environ.get("ADMIN_ENABLED", "False").lower() in {"1", "true", "yes", "on"}
)
if _admin_actif:
    urlpatterns.append(path("admin/", admin.site.urls))
