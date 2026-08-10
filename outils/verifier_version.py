#!/usr/bin/env python3
"""
outils/verifier_version.py — Garde-fou de la règle G-02 (version unique).

Échoue (code 1) si :
  * le fichier VERSION est absent, vide ou non sémantique ;
  * apps/poste-client/package.json déclare une version différente ;
  * une version littérale (ex. "2.1.0") est écrite en dur dans le code source.

Usage : python outils/verifier_version.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
LITTERAL = re.compile(r"""["']\d+\.\d+\.\d+["']""")

# Fichiers autorisés à contenir une version littérale (valeurs de repli, tests,
# verrous de dépendances, migrations générées).
EXCLUS = (
    "package-lock.json",
    "VERSION",
    "CHANGELOG.md",
    "verifier_version.py",
    "version.py",
    "version_vue.py",
    "version.ts",
    "version.test.ts",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.cfg",
    "package.json",
)
REPERTOIRES_EXCLUS = {"node_modules", ".git", "dist", "build", "migrations", "__pycache__", ".venv"}


def erreurs() -> list[str]:
    problemes: list[str] = []

    fichier = RACINE / "VERSION"
    if not fichier.is_file():
        return ["VERSION : fichier absent à la racine du dépôt."]
    version = fichier.read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        problemes.append(f"VERSION : « {version} » n'est pas une version sémantique valide.")

    package = RACINE / "apps" / "poste-client" / "package.json"
    if package.is_file():
        declaree = json.loads(package.read_text(encoding="utf-8")).get("version")
        if declaree != version:
            problemes.append(
                f"apps/poste-client/package.json : version « {declaree} » ≠ VERSION « {version} »."
            )

    for chemin in RACINE.rglob("*"):
        if not chemin.is_file() or chemin.suffix not in {".py", ".ts", ".tsx"}:
            continue
        if REPERTOIRES_EXCLUS & set(chemin.relative_to(RACINE).parts):
            continue
        if chemin.name in EXCLUS:
            continue
        for numero, ligne in enumerate(chemin.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if LITTERAL.search(ligne) and "version" in ligne.lower():
                problemes.append(
                    f"{chemin.relative_to(RACINE)}:{numero} : version codée en dur — "
                    "utiliser pharmapp.version / @/lib/version."
                )
    return problemes


def main() -> int:
    problemes = erreurs()
    if problemes:
        print("Cohérence de version : ÉCHEC")
        for p in problemes:
            print(f"  - {p}")
        return 1
    print(f"Cohérence de version : OK ({(RACINE / 'VERSION').read_text().strip()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
