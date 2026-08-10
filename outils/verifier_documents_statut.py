#!/usr/bin/env python3
"""
outils/verifier_documents_statut.py — Garde-fou de la règle G-03.

Un seul journal (CHANGELOG.md) et un seul état (docs/ETAT_DU_PROJET.md).
Ce contrôle échoue si un document de statut concurrent réapparaît dans le dépôt
(rapport de release, correctifs, état d'étape, audit ad hoc…).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

MOTIFS_INTERDITS = [
    re.compile(r"^RAPPORT[_-].*\.md$", re.I),
    re.compile(r"^CORRECTIFS?[_-].*\.md$", re.I),
    re.compile(r"^RELEASE[_-].*\.md$", re.I),
    re.compile(r"^PHASE\d[_-].*\.md$", re.I),
    re.compile(r"^ETAPE\d+.*\.md$", re.I),
    re.compile(r"^STATUS\.md$", re.I),
    re.compile(r"^AVANCEMENT.*\.md$", re.I),
]
AUTORISES = {
    RACINE / "CHANGELOG.md",
    RACINE / "docs" / "ETAT_DU_PROJET.md",
}
REPERTOIRES_EXCLUS = {"node_modules", ".git", "dist", "build", ".venv"}


def main() -> int:
    fautifs: list[Path] = []
    changelogs: list[Path] = []
    for chemin in RACINE.rglob("*.md"):
        relatif = chemin.relative_to(RACINE)
        if REPERTOIRES_EXCLUS & set(relatif.parts):
            continue
        if chemin in AUTORISES:
            continue
        if chemin.name.upper() == "CHANGELOG.MD":
            changelogs.append(relatif)
        if any(m.match(chemin.name) for m in MOTIFS_INTERDITS):
            fautifs.append(relatif)

    if fautifs or changelogs:
        print("Documents de statut : ÉCHEC (règle G-03)")
        for f in fautifs:
            print(f"  - document de statut concurrent : {f}")
        for c in changelogs:
            print(f"  - changelog secondaire : {c} (un seul CHANGELOG.md à la racine)")
        print("  → fusionner le contenu dans CHANGELOG.md / docs/ETAT_DU_PROJET.md puis supprimer.")
        return 1
    print("Documents de statut : OK (un changelog, un état du projet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
