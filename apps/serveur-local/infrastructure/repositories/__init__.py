# Couche Repository — isole l'accès aux données de la logique métier
from .base import DepotAbstrait
from .ventes import DepotVente
from .stocks import DepotStock
from .clients import DepotClient
from .catalogue import DepotMedicament, DepotLot
from .audit import DepotJournalAudit

__all__ = [
    "DepotAbstrait",
    "DepotVente",
    "DepotStock",
    "DepotClient",
    "DepotMedicament",
    "DepotLot",
    "DepotJournalAudit",
]
