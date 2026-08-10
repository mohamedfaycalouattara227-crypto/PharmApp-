"""Alias FR conforme à la convention du projet (modeles.py ↔ models.py)."""

from .models import (  # noqa: F401
    Fournisseur,
    StatutBonCommande,
    BonCommande,
    LigneBonCommande,
    ReceptionBonCommande,
    LigneReception,
)
