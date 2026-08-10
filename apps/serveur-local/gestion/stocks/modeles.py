"""gestion/stocks/modeles.py — Alias français vers models.py."""
from gestion.stocks.models import (  # noqa: F401
    MouvementStock,
    TypeMouvement,
    AlerteStock,
    NiveauAlerte,
    Inventaire,
    StatutInventaire,
    LigneInventaire,
)
