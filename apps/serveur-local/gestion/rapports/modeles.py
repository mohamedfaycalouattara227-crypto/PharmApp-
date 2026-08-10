"""gestion/rapports/modeles.py — Alias français vers models.py."""
from gestion.rapports.models import TypeRapport  # noqa: F401
try:
    from gestion.rapports.models import RapportGenere  # noqa: F401
except ImportError:
    pass
