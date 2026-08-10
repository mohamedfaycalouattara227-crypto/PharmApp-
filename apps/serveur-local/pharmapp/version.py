"""
pharmapp/version.py — Source unique de vérité de la version applicative.

La version est lue depuis le fichier ``VERSION`` situé à la racine du dépôt
monorepo. Aucun numéro de version ne doit être écrit en dur ailleurs dans le
code : toute duplication est un défaut bloquant (cf. outils/verifier_version.py).

Ordre de résolution :
  1. variable d'environnement ``PHARMAPP_VERSION`` (injectée par l'image Docker) ;
  2. fichier ``VERSION`` remonté depuis ce module jusqu'à la racine du dépôt ;
  3. valeur de repli ``0.0.0-inconnue`` (jamais acceptable en production).
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

_REPLI = "0.0.0-inconnue"


def _lire_fichier_version() -> str | None:
    depart = Path(__file__).resolve()
    for parent in depart.parents:
        candidat = parent / "VERSION"
        if candidat.is_file():
            valeur = candidat.read_text(encoding="utf-8").strip()
            if valeur:
                return valeur
    return None


@lru_cache(maxsize=1)
def version_applicative() -> str:
    """Retourne la version sémantique de l'application (ex. ``1.0.0``)."""
    depuis_env = os.environ.get("PHARMAPP_VERSION", "").strip()
    if depuis_env:
        return depuis_env
    return _lire_fichier_version() or _REPLI


@lru_cache(maxsize=1)
def revision_git() -> str:
    """Retourne le SHA court du commit déployé, ou ``inconnue``."""
    depuis_env = os.environ.get("PHARMAPP_COMMIT", "").strip()
    if depuis_env:
        return depuis_env[:12]
    try:
        sortie = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return sortie.stdout.strip() or "inconnue"
    except Exception:  # pragma: no cover - environnement sans git (image Docker)
        return "inconnue"


def date_construction() -> str:
    """Horodatage ISO 8601 injecté au build (``PHARMAPP_BUILD_DATE``)."""
    return os.environ.get("PHARMAPP_BUILD_DATE", "inconnue")


__version__ = version_applicative()
