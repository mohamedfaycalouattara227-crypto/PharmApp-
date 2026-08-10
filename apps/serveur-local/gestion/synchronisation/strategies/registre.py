"""Registre des stratégies : mappe un modèle Django à sa stratégie."""

from typing import Dict

from .base import StrategieResolution
from .catalogue import StrategieCatalogue
from .clients import StrategieClients
from .stock import StrategieStockAdditif
from .utilisateurs import StrategieUtilisateurs
from .ventes import StrategieVentesImmuable


class RegistreStrategies:
    """
    Registre statique. Toute nouvelle catégorie de donnée synchronisée
    doit enregistrer sa stratégie ici pour éviter le comportement par
    défaut « conflit détecté mais non résolu » — ce qui contrevient au
    §2.5 du cahier des charges.
    """

    _mapping: Dict[str, StrategieResolution] = {
        # Ventes
        "ventes.vente":                 StrategieVentesImmuable(),
        "ventes.lignevente":            StrategieVentesImmuable(),
        "ventes.cloturecaisse":         StrategieVentesImmuable(),
        # Stock
        "catalogue.lot":                StrategieStockAdditif(),
        "stocks.mouvementstock":        StrategieVentesImmuable(),  # journal immuable
        # Catalogue / prix
        "catalogue.medicament":         StrategieCatalogue(),
        "catalogue.categorieproduit":   StrategieCatalogue(),
        # Clients
        "clients.client":               StrategieClients(),
        # Utilisateurs
        "authentification.utilisateur": StrategieUtilisateurs(),
        # Fournisseurs — pilotés par le local (source première)
        "fournisseurs.fournisseur":     StrategieCatalogue(),
        "fournisseurs.boncommande":     StrategieCatalogue(),
    }

    @classmethod
    def obtenir(cls, cle_modele: str) -> StrategieResolution:
        try:
            return cls._mapping[cle_modele.lower()]
        except KeyError as e:
            raise LookupError(
                f"Aucune stratégie de résolution de conflit définie pour « {cle_modele} ». "
                "Ajouter une entrée dans RegistreStrategies avant de synchroniser ce type."
            ) from e

    @classmethod
    def enregistrer(cls, cle_modele: str, strategie: StrategieResolution) -> None:
        cls._mapping[cle_modele.lower()] = strategie


def obtenir_strategie(cle_modele: str) -> StrategieResolution:
    """API publique — wrapper autour du registre."""
    return RegistreStrategies.obtenir(cle_modele)
