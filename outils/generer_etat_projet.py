#!/usr/bin/env python3
"""
outils/generer_etat_projet.py — Régénère l'en-tête de docs/ETAT_DU_PROJET.md
à chaque jalon (règle G-03) : version, jalon courant, date, tableau des étapes
et synthèse des écarts critiques extraite de docs/DETTE.md.

    python outils/generer_etat_projet.py --jalon 01 --etat-etape "En cours"
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ETAT = RACINE / "docs" / "ETAT_DU_PROJET.md"
DETTE = RACINE / "docs" / "DETTE.md"
SUIVI = RACINE / "docs" / "SUIVI_ETAPES.md"

ETAPES = {
    "00": "Gel, unification et gouvernance du code",
    "01": "Durcissement de la CI et remise au vert de la suite de tests",
    "02": "Intégrité des données : migrations et contraintes",
    "03": "Complétude fonctionnelle Phase 1",
    "04": "Intégration matérielle (ticket, code-barres, tiroir)",
    "05": "Durcissement du poste client",
    "06": "Résilience hors-ligne",
    "07": "Audit de sécurité (OWASP ASVS L2)",
    "08": "Épreuve de la synchronisation cloud",
    "09": "Exploitation : sauvegarde, restauration, supervision",
    "10": "Industrialisation du déploiement",
    "11": "Performance",
    "12": "Recette formelle en conditions d'officine",
    "13": "Conformité réglementaire",
    "14": "Déploiement pilote",
}

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def ecarts_critiques() -> list[tuple[str, str]]:
    resultats: list[tuple[str, str]] = []
    for ligne in DETTE.read_text(encoding="utf-8").splitlines():
        if not ligne.startswith("| DT-"):
            continue
        cellules = [c.strip() for c in ligne.strip("|").split("|")]
        if len(cellules) >= 7 and cellules[2] == "Critique" and cellules[6] != "Fermé":
            resultats.append((cellules[0], cellules[1]))
    return resultats


def main() -> int:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--jalon", default=None, help="numéro d'étape courante, ex. 01")
    args = parseur.parse_args()

    version = (RACINE / "VERSION").read_text(encoding="utf-8").strip()
    texte = ETAT.read_text(encoding="utf-8")

    jalon = args.jalon
    if jalon is None:
        trouve = re.search(r"\*\*Jalon courant :\*\* ÉTAPE (\d{2})", texte)
        jalon = trouve.group(1) if trouve else "00"
    suivant = f"{int(jalon) + 1:02d}" if f"{int(jalon) + 1:02d}" in ETAPES else jalon

    aujourdhui = dt.date.today()
    date_fr = f"{aujourdhui.day} {MOIS[aujourdhui.month - 1]} {aujourdhui.year}"

    remplacements = {
        r"- \*\*Version du dépôt :\*\* .*": f"- **Version du dépôt :** {version}",
        r"- \*\*Jalon courant :\*\* .*": f"- **Jalon courant :** ÉTAPE {jalon} — {ETAPES[jalon]}",
        r"- \*\*Prochain jalon :\*\* .*": f"- **Prochain jalon :** ÉTAPE {suivant} — {ETAPES[suivant]}",
        r"- \*\*Généré le :\*\* .*": f"- **Généré le :** {date_fr}",
    }
    for motif, valeur in remplacements.items():
        texte = re.sub(motif, valeur, texte, count=1)

    ETAT.write_text(texte, encoding="utf-8")

    print(f"docs/ETAT_DU_PROJET.md régénéré — version {version}, jalon {jalon} ({date_fr}).")
    critiques = ecarts_critiques()
    print(f"Écarts critiques ouverts : {len(critiques)}")
    for identifiant, libelle in critiques:
        print(f"  - {identifiant} : {libelle[:80]}…")
    if not SUIVI.is_file():
        print("AVERTISSEMENT : docs/SUIVI_ETAPES.md introuvable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
