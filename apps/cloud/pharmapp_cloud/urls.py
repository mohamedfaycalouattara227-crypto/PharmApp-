"""
pharmapp_cloud/urls.py — Routage central du Cloud PharmApp.

    /api/cloud/…      — API multi-officines
    /api/v1/version/  — identité de build (non authentifié, ÉTAPE 00)
"""

from django.urls import path, include

from api.version_vue import VueVersion

urlpatterns = [
    path("api/v1/version/", VueVersion.as_view(), name="version"),
    path("api/cloud/", include("api.urls")),
]
