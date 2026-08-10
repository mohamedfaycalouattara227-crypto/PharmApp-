"""api/healthcheck.py — Endpoints de santé (liveness / readiness)."""

from __future__ import annotations

from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def liveness(_request):
    """Le processus répond — pas de dépendance externe testée."""
    return JsonResponse({"statut": "vivant"})


@require_GET
@never_cache
def readiness(_request):
    """Le service est prêt : base de données OK + cache OK."""
    problemes: list[str] = []

    for nom in connections:
        try:
            connections[nom].cursor().execute("SELECT 1")
        except OperationalError as exc:  # pragma: no cover — dépendant infra
            problemes.append(f"db:{nom}:{exc}")

    try:
        from django.core.cache import cache

        cache.set("readiness_probe", "1", 5)
        if cache.get("readiness_probe") != "1":
            problemes.append("cache:miss")
    except Exception as exc:  # pragma: no cover
        problemes.append(f"cache:{exc}")

    if problemes:
        return JsonResponse({"statut": "degrade", "problemes": problemes}, status=503)
    return JsonResponse({"statut": "pret"})
