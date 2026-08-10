"""
gestion/audit/vues.py
Vues DRF pour le journal d'audit — lecture seule.
"""

from rest_framework import viewsets
from rest_framework.response import Response

from api.permissions import EstTitulaire


class VueJournalAudit(viewsets.ReadOnlyModelViewSet):
    """
    Journal d'audit — lecture seule (immuable).
    Accessible aux titulaires uniquement.
    """

    permission_classes = [EstTitulaire]

    def get_queryset(self):
        from gestion.audit.models import JournalAudit
        qs = JournalAudit.objects.all().order_by("-cree_le")
        type_action = self.request.query_params.get("type_action")
        if type_action:
            qs = qs.filter(type_action=type_action)
        severite = self.request.query_params.get("severite")
        if severite:
            qs = qs.filter(severite=severite)
        utilisateur_id = self.request.query_params.get("utilisateur_id")
        if utilisateur_id:
            qs = qs.filter(utilisateur_id=utilisateur_id)
        return qs

    def get_serializer_class(self):
        from gestion.audit.serialiseurs import JournalAuditSerialiseur
        return JournalAuditSerialiseur
