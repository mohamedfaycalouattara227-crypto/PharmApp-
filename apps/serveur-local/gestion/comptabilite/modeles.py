"""gestion/comptabilite/modeles.py — Alias français vers models.py."""
from gestion.comptabilite.models import TypeEcriture  # noqa: F401
try:
    from gestion.comptabilite.models import EcritureComptable  # noqa: F401
except ImportError:
    pass
