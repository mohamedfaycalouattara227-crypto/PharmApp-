"""
gestion/synchronisation/resolveur.py

Résolveur de conflits qui applique la stratégie enregistrée pour un type
de donnée puis met à jour le modèle `ConflitSynchronisation` en base.
Ce module est le point d'entrée appelé par la tâche Celery de sync
(remplace la logique historique qui se contentait de *détecter*).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from gestion.synchronisation.models import (
    ConflitSynchronisation,
    StatutConflit,
)
from gestion.synchronisation.strategies import (
    DecisionConflit,
    ResultatConflit,
    obtenir_strategie,
)

logger = logging.getLogger("pharmapp.synchronisation.resolveur")


class ResolveurConflit:
    """Résout un conflit à partir du modèle et des payloads locaux/cloud."""

    def __init__(self, contexte: Optional[Dict[str, Any]] = None):
        self.contexte = contexte or {}

    @transaction.atomic
    def resoudre(self, conflit: ConflitSynchronisation) -> ResultatConflit:
        strategie = obtenir_strategie(conflit.modele)
        resultat = strategie.resoudre(
            donnees_locales=conflit.donnees_locales,
            donnees_cloud=conflit.donnees_cloud,
            contexte=self.contexte,
        )
        conflit.statut = _mapper_statut(resultat.decision)
        conflit.resolu_par = resultat.strategie
        conflit.resolu_le = timezone.now()
        conflit.notes = (
            f"[{resultat.strategie}] {resultat.raison}"
            + (f"\nAlerte titulaire : oui" if resultat.alerte_titulaire else "")
        )
        conflit.save(
            update_fields=["statut", "resolu_par", "resolu_le", "notes", "modifie_le"]
        )
        logger.info(
            "Conflit %s (%s) → %s [%s]",
            conflit.id, conflit.modele, resultat.decision.value, resultat.strategie,
        )
        return resultat


def _mapper_statut(decision: DecisionConflit) -> str:
    return {
        DecisionConflit.CONSERVER_LOCAL: StatutConflit.RESOLU_LOCAL,
        DecisionConflit.APPLIQUER_CLOUD: StatutConflit.RESOLU_CLOUD,
        DecisionConflit.FUSIONNER:       StatutConflit.RESOLU_CLOUD,
        DecisionConflit.ESCALADER:       StatutConflit.NON_RESOLU,
    }[decision]
