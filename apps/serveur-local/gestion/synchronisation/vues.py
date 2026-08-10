"""
gestion/synchronisation/vues.py — Étape 15 (mise à jour)

Ajout : GET /api/synchronisation/etat/ — état détaillé avec ping Supabase.
"""

import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstTitulaire
from gestion.sync.services import ServiceSynchronisation
from gestion.synchronisation.models import EtatSynchronisation

logger = logging.getLogger("pharmapp.synchronisation")


class VueSynchronisation(viewsets.ViewSet):
    """Contrôle de la synchronisation locale ↔ cloud."""

    permission_classes = [EstAuthentifie]

    def etat(self, request):
        """
        Retourne l'état courant de la synchronisation.
        GET /api/synchronisation/etat/

        Réponse :
          nb_en_attente         : int   — événements outbox EN_ATTENTE
          nb_en_echec           : int   — événements outbox ECHEC
          derniere_synchro_reussie : str|null — ISO datetime
          supabase_accessible   : bool  — ping Supabase (timeout 3s)
          conflits_non_resolus  : int
        """
        from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

        # Statistiques outbox
        nb_en_attente = EntreeOutbox.objects.filter(statut=StatutOutbox.EN_ATTENTE).count()
        nb_en_echec = EntreeOutbox.objects.filter(statut=StatutOutbox.ECHEC).count()

        # Dernière synchronisation réussie
        derniere_synchro = None
        try:
            service = ServiceSynchronisation()
            statut_sync = service.obtenir_statut()
            derniere_synchro = (
                statut_sync.derniere_sync_reussie.isoformat()
                if statut_sync.derniere_sync_reussie
                else None
            )
            conflits = statut_sync.conflits_non_resolus
        except Exception as exc:
            logger.warning("Impossible d'obtenir le statut de synchronisation : %s", exc)
            conflits = 0

        # Ping Supabase
        supabase_accessible = _ping_supabase()

        return Response({
            "nb_en_attente": nb_en_attente,
            "nb_en_echec": nb_en_echec,
            "derniere_synchro_reussie": derniere_synchro,
            "supabase_accessible": supabase_accessible,
            "conflits_non_resolus": conflits,
        })

    @action(detail=False, methods=["post"], permission_classes=[EstTitulaire])
    def rejouer(self, request):
        """Remet en file les événements en échec."""
        service = ServiceSynchronisation()
        count = service.rejouer_echecs()
        return Response({"rejoues": count})


def _ping_supabase() -> bool:
    """
    Vérifie si Supabase est accessible en effectuant un HEAD sur /rest/v1/.
    Timeout : 3 secondes. Ne lève jamais d'exception.
    """
    from django.conf import settings
    supabase_url = getattr(settings, "SUPABASE_URL", "")
    if not supabase_url:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/",
            method="HEAD",
            headers={
                "apikey": getattr(settings, "SUPABASE_ANON_KEY", ""),
            },
        )
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        # Supabase inaccessible — situation normale en mode offline.
        return False


class VueConflitSync(viewsets.ModelViewSet):
    """Gestion des conflits de synchronisation."""

    permission_classes = [EstTitulaire]

    def get_queryset(self):
        from gestion.synchronisation.models import ConflitSynchronisation
        qs = ConflitSynchronisation.objects.all().order_by("-cree_le")
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def get_serializer_class(self):
        from gestion.synchronisation.serialiseurs import ConflitSynchronisationSerialiseur
        return ConflitSynchronisationSerialiseur
