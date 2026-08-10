"""
api/urls.py — Routage central du Cloud PharmApp.

Phase 1 :
  POST   /api/cloud/officines/                        Provisionner une officine (admin)
  GET    /api/cloud/officines/                        Lister les officines (admin)
  GET    /api/cloud/officines/{id}/                   Détail officine (admin)
  POST   /api/cloud/officines/{id}/regenerer-cle/     Rotation de clé (admin)
  POST   /api/cloud/officines/{id}/suspendre/         Suspendre (admin)
  POST   /api/cloud/officines/{id}/reactiver/         Réactiver (admin)
  POST   /api/cloud/sync/evenements/                  Ingestion événements (officine)
  GET    /api/cloud/sync/a-recuperer/                 Événements descendants (officine) — Phase 3
  GET    /api/cloud/healthz/                          Liveness (public)
  GET    /api/cloud/readyz/                           Readiness DB (public)
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.identite.vues import VueOfficine
from apps.synchronisation.vues import VueIngestionEvenement
from api.healthcheck import vue_liveness, vue_readiness

router = DefaultRouter()
router.register(r"officines", VueOfficine, basename="officine")

urlpatterns = [
    # Santé (public — pour les healthchecks Docker/K8s)
    path("healthz/", vue_liveness,  name="cloud-liveness"),
    path("readyz/",  vue_readiness, name="cloud-readiness"),

    # Synchronisation — ingestion (officine authentifiée)
    path("sync/evenements/", VueIngestionEvenement.as_view(), name="sync-ingestion"),

    # Router (officines — admin uniquement)
    *router.urls,
]
