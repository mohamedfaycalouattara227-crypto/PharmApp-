"""Contrats de base pour les stratégies de résolution de conflit."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


class DecisionConflit(str, Enum):
    CONSERVER_LOCAL = "conserver_local"
    APPLIQUER_CLOUD = "appliquer_cloud"
    FUSIONNER       = "fusionner"
    ESCALADER       = "escalader"          # nécessite intervention humaine (titulaire)


@dataclass
class ResultatConflit:
    """Résultat d'une résolution : décision + payload final + trace."""

    decision: DecisionConflit
    payload_final: Dict[str, Any]
    strategie: str
    raison: str = ""
    champs_divergents: List[str] = field(default_factory=list)
    alerte_titulaire: bool = False

    def est_automatique(self) -> bool:
        return self.decision is not DecisionConflit.ESCALADER


class StrategieResolution(Protocol):
    """Contrat commun des stratégies de résolution."""

    nom: str

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        ...
