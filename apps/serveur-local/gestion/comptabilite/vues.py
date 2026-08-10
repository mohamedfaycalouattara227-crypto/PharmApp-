"""
gestion/comptabilite/vues.py
Vues DRF pour la comptabilité.
"""

import logging

from rest_framework import viewsets
from api.permissions import EstTitulaire

logger = logging.getLogger("pharmapp.comptabilite")


class VueComptabilite(viewsets.ModelViewSet):
    """Gestion des écritures comptables — réservé au titulaire."""

    permission_classes = [EstTitulaire]

    def get_queryset(self):
        try:
            from gestion.comptabilite.models import EcritureComptable
            return EcritureComptable.objects.all().order_by("-cree_le")
        except Exception as exc:
            logger.warning("EcritureComptable indisponible (migration ?) : %s", exc)
            return []

    def get_serializer_class(self):
        try:
            from gestion.comptabilite.serialiseurs import EcritureComptableSerialiseur
            return EcritureComptableSerialiseur
        except Exception as exc:
            logger.warning("EcritureComptableSerialiseur indisponible : %s", exc)
            from rest_framework import serializers
            return serializers.Serializer
