#!/usr/bin/env python3
"""
outils/verifier_commit.py — Validation Conventional Commits (règle G-07).

Utilisé par le hook `commit-msg` et par la CI (sur tous les commits d'une PR).

    python outils/verifier_commit.py .git/COMMIT_EDITMSG
    python outils/verifier_commit.py --message "feat(ventes): plafonner la remise"
"""

from __future__ import annotations

import argparse
import re
import sys

TYPES = (
    "feat", "fix", "perf", "refactor", "docs", "test",
    "build", "ci", "chore", "revert", "security",
)
PORTEES = (
    "serveur-local", "poste-client", "cloud", "infra", "docs", "outils", "ci", "deps",
    "ventes", "stocks", "ordonnances", "audit", "sync", "rapports", "parametrage",
    "fournisseurs", "produits-controles", "comptabilite", "clients", "catalogue",
    "auth", "cloture", "release",
)
ENTETE = re.compile(
    rf"^(?P<type>{'|'.join(TYPES)})(?:\((?P<portee>[a-z0-9-]+)\))?(?P<casse>!)?: (?P<sujet>.+)$"
)
TOLERES = ("Merge ", "Revert ", "fixup!", "squash!")


def valider(message: str) -> list[str]:
    lignes = [l for l in message.splitlines() if not l.startswith("#")]
    if not lignes or not lignes[0].strip():
        return ["message de commit vide."]
    entete = lignes[0].strip()
    if entete.startswith(TOLERES):
        return []

    problemes: list[str] = []
    correspondance = ENTETE.match(entete)
    if not correspondance:
        return [
            f"en-tête non conforme : « {entete} »",
            f"format attendu : <type>(<portée>): <sujet>   types : {', '.join(TYPES)}",
        ]
    if len(entete) > 72:
        problemes.append(f"en-tête de {len(entete)} caractères (maximum 72).")
    portee = correspondance.group("portee")
    if portee and portee not in PORTEES:
        problemes.append(f"portée inconnue « {portee} » — voir docs/GOUVERNANCE.md §4.")
    sujet = correspondance.group("sujet")
    if sujet[0].isupper():
        problemes.append("le sujet ne commence pas par une majuscule.")
    if sujet.endswith("."):
        problemes.append("le sujet ne se termine pas par un point.")
    if len(lignes) > 1 and lignes[1].strip():
        problemes.append("une ligne vide doit séparer l'en-tête du corps.")
    return problemes


def main() -> int:
    parseur = argparse.ArgumentParser(description="Vérifie un message de commit.")
    parseur.add_argument("fichier", nargs="?", help="chemin du fichier de message")
    parseur.add_argument("--message", help="message fourni directement")
    args = parseur.parse_args()

    if args.message is not None:
        message = args.message
    elif args.fichier:
        with open(args.fichier, encoding="utf-8") as f:
            message = f.read()
    else:
        message = sys.stdin.read()

    problemes = valider(message)
    if problemes:
        print("Message de commit refusé (règle G-07) :")
        for p in problemes:
            print(f"  - {p}")
        print("\nExemple valide :\n  fix(sync): rejouer les evenements outbox apres reconnexion\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
