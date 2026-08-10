"""
api/exceptions_handler.py
Gestionnaire d'exceptions DRF centralisé pour PharmApp.
Transforme toutes les exceptions en réponses JSON cohérentes.
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from gestion.exceptions import ExceptionPharmApp

logger = logging.getLogger("pharmapp.api")


def gerer_exception(exc, context):
    """
    Gestionnaire d'exceptions DRF personnalisé.
    1. Traite d'abord les exceptions DRF standard.
    2. Transforme les ExceptionPharmApp en réponses structurées.
    3. Log les erreurs serveur (5xx).
    """
    # Laisser DRF traiter ses propres exceptions en premier
    reponse = exception_handler(exc, context)

    if reponse is not None:
        # Reformater la réponse DRF avec notre structure
        reponse.data = {
            "erreur": _code_statut_vers_code_erreur(reponse.status_code),
            "message": _extraire_message(reponse.data),
            "details": reponse.data if isinstance(reponse.data, dict) else {"non_field_errors": reponse.data},
        }
        return reponse

    # Exceptions métier PharmApp
    if isinstance(exc, ExceptionPharmApp):
        logger.warning(
            "Exception métier [%s] : %s — Vue : %s",
            exc.code_erreur,
            exc.message,
            context.get("view", "?"),
        )
        return Response(
            exc.to_dict(),
            status=exc.statut_http,
        )

    # Exceptions non gérées → 500
    logger.error(
        "Exception non gérée dans %s : %s",
        context.get("view", "?"),
        str(exc),
        exc_info=True,
    )
    return Response(
        {
            "erreur": "erreur_serveur",
            "message": "Une erreur interne est survenue. Veuillez contacter l'administrateur.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _extraire_message(data) -> str:
    """Extrait un message lisible depuis les données d'erreur DRF."""
    if isinstance(data, str):
        return data
    if isinstance(data, list) and data:
        return str(data[0])
    if isinstance(data, dict):
        for cle in ("detail", "message", "non_field_errors"):
            if cle in data:
                val = data[cle]
                return str(val[0]) if isinstance(val, list) else str(val)
        premier = next(iter(data.values()), None)
        if premier:
            return str(premier[0]) if isinstance(premier, list) else str(premier)
    return "Erreur de validation."


def _code_statut_vers_code_erreur(statut_http: int) -> str:
    mapping = {
        400: "requete_invalide",
        401: "non_authentifie",
        403: "acces_refuse",
        404: "ressource_introuvable",
        405: "methode_non_autorisee",
        409: "conflit",
        429: "trop_de_requetes",
        500: "erreur_serveur",
    }
    return mapping.get(statut_http, f"erreur_{statut_http}")
