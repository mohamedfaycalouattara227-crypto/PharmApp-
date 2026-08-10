"""
gestion/synchronisation/strategies/__init__.py

Registre des stratégies de résolution de conflits par type de donnée,
conforme au tableau §2.5 du cahier des charges :

    Ventes (immuable)      → cloud autoritaire
    Stock (numérique)      → merge additif (deltas)
    Catalogue / prix       → last-writer-wins horodaté
    Fiches clients         → merge champ par champ, alerte titulaire si divergence
    Utilisateurs / rôles   → cloud autoritaire (jamais rétrogradation locale silencieuse)

Toute stratégie implémente `resoudre(donnees_locales, donnees_cloud) -> ResultatConflit`.
"""

from .base import StrategieResolution, ResultatConflit, DecisionConflit
from .catalogue import StrategieCatalogue
from .clients import StrategieClients
from .registre import RegistreStrategies, obtenir_strategie
from .stock import StrategieStockAdditif
from .utilisateurs import StrategieUtilisateurs
from .ventes import StrategieVentesImmuable

__all__ = [
    "StrategieResolution",
    "ResultatConflit",
    "DecisionConflit",
    "RegistreStrategies",
    "obtenir_strategie",
    "StrategieVentesImmuable",
    "StrategieStockAdditif",
    "StrategieCatalogue",
    "StrategieClients",
    "StrategieUtilisateurs",
]
