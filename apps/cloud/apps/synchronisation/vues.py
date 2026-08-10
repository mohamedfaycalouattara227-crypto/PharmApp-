"""
apps/synchronisation/vues.py
Vues DRF pour la synchronisation Cloud PharmApp.

POST /api/cloud/sync/evenements/
  Ingestion d'un événement depuis un serveur local authentifié.
  Retourne 201 (nouveau) ou 409 (déjà connu — idempotence).
"""

import logging

from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.identite.permissions import EstOfficineActive
from apps.synchronisation.serialiseurs import (
    EvenementEntrantSerialiseur,
    EvenementReponseSerialiseur,
)
from apps.synchronisation.services import DonneesEvenement, ServiceIngestion

logger = logging.getLogger("pharmapp_cloud.synchronisation")


class VueIngestionEvenement(APIView):
    """
    POST /api/cloud/sync/evenements/

    Reçoit un événement de synchronisation depuis un serveur local.

    Authentification : clé API officine (X-Api-Key)
    Permission      : officine active avec abonnement valide
    Idempotence     : un UUID déjà connu retourne 409 sans erreur
    Débit           : throttle "ingestion" (1000/min)

    Corps attendu :
    {
      "uuid": "550e8400-...",
      "type_evenement": "VENTE_CREEE",
      "version_schema": 1,
      "timestamp_local": "2026-07-21T10:30:00Z",
      "charge_utile": { ... }
    }

    Réponses :
      201 { "uuid": "...", "statut": "reçu",      "message": "..." }
      409 { "uuid": "...", "statut": "déjà_connu", "message": "..." }
      400 Validation échouée
      401 Clé API absente/invalide
      403 Officine inactive ou abonnement expiré
    """

    permission_classes = [EstOfficineActive]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = "ingestion"

    def post(self, request) -> Response:
        serialiseur = EvenementEntrantSerialiseur(data=request.data)
        if not serialiseur.is_valid():
            return Response(serialiseur.errors, status=400)

        donnees_validees = serialiseur.validated_data
        officine = request.user  # instance Officine, résolue par AuthenticationParCleApi

        donnees = DonneesEvenement(
            uuid=donnees_validees["uuid"],
            type_evenement=donnees_validees["type_evenement"],
            version_schema=donnees_validees["version_schema"],
            timestamp_local=donnees_validees["timestamp_local"],
            charge_utile=donnees_validees["charge_utile"],
        )

        resultat = ServiceIngestion.ingerer(officine=officine, donnees=donnees)

        code_http = 409 if resultat.statut == "déjà_connu" else 201

        reponse_serialiseur = EvenementReponseSerialiseur(resultat)
        return Response(reponse_serialiseur.data, status=code_http)
