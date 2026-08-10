"""
apps/identite/vues.py
Vues DRF pour la gestion des Officines.

Endpoints :
  POST   /api/cloud/officines/              Provisionner une officine (admin)
  GET    /api/cloud/officines/              Lister les officines (admin)
  GET    /api/cloud/officines/{id}/         Détail officine (admin)
  POST   /api/cloud/officines/{id}/regenerer-cle/  Rotation de clé (admin)
  POST   /api/cloud/officines/{id}/suspendre/       Suspendre (admin)
  POST   /api/cloud/officines/{id}/reactiver/       Réactiver (admin)
"""

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import ViewSet

from apps.identite.models import Officine
from apps.identite.permissions import EstAdminCloud
from apps.identite.serialiseurs import (
    OfficineCreationSerialiseur,
    OfficineDetailSerialiseur,
    OfficineListeSerialiseur,
    OfficineProvisionnementSerialiseur,
    RegenerationCleSerialiseur,
)
from apps.identite.services import ServiceOfficine

logger = logging.getLogger("pharmapp_cloud.identite")


class VueOfficine(ViewSet):
    """
    ViewSet de gestion des Officines — accès réservé à l'admin cloud.

    Toutes les actions nécessitent EstAdminCloud (token admin, pas clé API).
    """

    permission_classes = [EstAdminCloud]
    throttle_scope = "provisionnement"

    # ─── Liste ────────────────────────────────────────────────────────────────
    def list(self, request) -> Response:
        """GET /api/cloud/officines/ — liste de toutes les officines."""
        officines = Officine.objects.order_by("code")
        serialiseur = OfficineListeSerialiseur(officines, many=True)
        return Response(serialiseur.data)

    # ─── Détail ───────────────────────────────────────────────────────────────
    def retrieve(self, request, pk=None) -> Response:
        """GET /api/cloud/officines/{id}/ — détail d'une officine."""
        try:
            officine = Officine.objects.get(pk=pk)
        except Officine.DoesNotExist:
            return Response(
                {"detail": "Officine introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serialiseur = OfficineDetailSerialiseur(officine)
        return Response(serialiseur.data)

    # ─── Création / provisionnement ───────────────────────────────────────────
    def create(self, request) -> Response:
        """
        POST /api/cloud/officines/ — provisionner une nouvelle officine.

        Retourne la clé API complète UNE SEULE FOIS.
        L'admin doit la transmettre immédiatement et de façon sécurisée
        au responsable de la pharmacie.
        """
        serialiseur = OfficineCreationSerialiseur(data=request.data)
        if not serialiseur.is_valid():
            return Response(serialiseur.errors, status=status.HTTP_400_BAD_REQUEST)

        donnees = serialiseur.validated_data
        try:
            resultat = ServiceOfficine.provisionner(
                nom=donnees["nom"],
                code=donnees["code"],
                ville=donnees.get("ville", ""),
                pays=donnees.get("pays", "Burkina Faso"),
                notes=donnees.get("notes", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        logger.info(
            "Officine provisionnée par l'admin",
            extra={"code": resultat.code, "officine_id": resultat.officine_id},
        )

        reponse_serialiseur = OfficineProvisionnementSerialiseur(resultat)
        return Response(reponse_serialiseur.data, status=status.HTTP_201_CREATED)

    # ─── Rotation de clé API ──────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="regenerer-cle")
    def regenerer_cle(self, request, pk=None) -> Response:
        """
        POST /api/cloud/officines/{id}/regenerer-cle/
        Révoque l'ancienne clé API et en génère une nouvelle.
        """
        try:
            resultat = ServiceOfficine.regenerer_cle_api(officine_id=pk)
        except Officine.DoesNotExist:
            return Response(
                {"detail": "Officine introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.warning(
            "Rotation de clé API par l'admin",
            extra={"officine_id": pk},
        )

        reponse_serialiseur = RegenerationCleSerialiseur(resultat)
        return Response(reponse_serialiseur.data, status=status.HTTP_200_OK)

    # ─── Suspension ───────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="suspendre")
    def suspendre(self, request, pk=None) -> Response:
        """POST /api/cloud/officines/{id}/suspendre/ — bloque l'officine."""
        raison = request.data.get("raison", "")
        try:
            ServiceOfficine.suspendre(officine_id=pk, raison=raison)
        except Officine.DoesNotExist:
            return Response(
                {"detail": "Officine introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Officine suspendue."}, status=status.HTTP_200_OK)

    # ─── Réactivation ─────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="reactiver")
    def reactiver(self, request, pk=None) -> Response:
        """POST /api/cloud/officines/{id}/reactiver/ — réactive l'officine."""
        try:
            ServiceOfficine.reactiver(officine_id=pk)
        except Officine.DoesNotExist:
            return Response(
                {"detail": "Officine introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Officine réactivée."}, status=status.HTTP_200_OK)
