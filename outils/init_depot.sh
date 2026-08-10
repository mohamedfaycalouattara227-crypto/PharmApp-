#!/usr/bin/env bash
# outils/init_depot.sh — Crée le dépôt Git unifié avec un commit initial normalisé.
#
# À exécuter UNE SEULE FOIS, depuis la racine du dépôt, après extraction de
# l'archive PharmApp v1.0.0 :
#     bash outils/init_depot.sh
#
# Idempotent : refuse de s'exécuter si un dépôt Git existe déjà.
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

if [ -d .git ]; then
  echo "Un dépôt Git existe déjà dans $RACINE — rien à faire."
  exit 0
fi

VERSION="$(tr -d '[:space:]' < VERSION)"

git init -q -b main
git config commit.template .gitmessage
git config core.hooksPath .githooks
git add -A
git -c core.hooksPath=/dev/null commit -q -F - <<EOF
chore(release): unifier les trois arborescences en un depot monorepo

Etape 00 de la feuille de route de mise en production.

- apps/serveur-local  : ancien pharmapp_fixed/backend
- apps/poste-client   : ancien pharmapp_fixed/frontend
- apps/cloud          : ancien pharmapp_cloud
- docs/, infra/, outils/ : gouvernance, deploiement, outillage

Version applicative unique lue depuis VERSION ($VERSION), exposee par
GET /api/v1/version/ et affichee en pied de page du poste client.
Rapports de statut concurrents supprimes au profit de CHANGELOG.md et
docs/ETAT_DU_PROJET.md.
EOF

git tag -a "v${VERSION}" -m "PharmApp v${VERSION} — socle unifie (etape 00)"
git branch develop

cat <<EOF

Dépôt initialisé.
  Branche par défaut : main (tag v${VERSION})
  Branche d'intégration : develop
  Hooks Git actifs : .githooks (commit-msg, pre-commit, pre-push)

Prochaines actions :
  1. git remote add origin <url-de-la-forge> && git push -u origin main develop --tags
  2. bash outils/proteger_branches.sh   (protection de main sur la forge)
  3. bash outils/creer_tableau_suivi.sh (tableau de suivi des 15 étapes)
EOF
