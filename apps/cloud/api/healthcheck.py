"""
api/healthcheck.py
Endpoints de santé pour les orchestrateurs (Docker, K8s).

GET /api/cloud/healthz/ → liveness  (l'app répond)
GET /api/cloud/readyz/  → readiness (l'app + la DB sont prêtes)
"""

from django.db import connection, OperationalError
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def vue_liveness(request) -> Response:
    """Liveness probe — retourne 200 si le process Django est actif."""
    return Response({"statut": "ok"})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def vue_readiness(request) -> Response:
    """
    Readiness probe — vérifie la connectivité DB.
    Retourne 200 si prêt à servir des requêtes, 503 sinon.
    """
    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
    except OperationalError as exc:
        return Response(
            {"statut": "erreur", "detail": "Base de données inaccessible."},
            status=503,
        )
    return Response({"statut": "ok", "db": "connectée"})
