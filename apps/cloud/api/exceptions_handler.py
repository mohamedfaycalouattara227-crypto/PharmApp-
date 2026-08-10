"""
api/exceptions_handler.py
Gestionnaire d'exceptions DRF unifié pour le Cloud PharmApp.
Retourne toujours du JSON structuré avec un champ "detail".
"""

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("pharmapp_cloud")


def gestionnaire_exceptions(exc, context):
    """
    Surcharge du gestionnaire DRF par défaut.
    - Log les erreurs 5xx avec le request_id.
    - Normalise la structure de réponse.
    """
    reponse = exception_handler(exc, context)

    if reponse is not None:
        if reponse.status_code >= 500:
            request = context.get("request")
            request_id = getattr(request, "request_id", "") if request else ""
            logger.error(
                "Erreur serveur non gérée",
                extra={
                    "request_id": request_id,
                    "status_code": reponse.status_code,
                    "exception": str(exc),
                },
            )

        # Normaliser la structure
        if not isinstance(reponse.data, dict) or "detail" not in reponse.data:
            reponse.data = {"detail": reponse.data}

    return reponse
