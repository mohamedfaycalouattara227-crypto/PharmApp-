#!/usr/bin/env bash
# outils/creer_tableau_suivi.sh — Crée le tableau de suivi unique des 15 étapes
# (GitHub Projects v2) : une carte par étape, avec son critère de sortie.
set -euo pipefail

PROPRIETAIRE="${1:?usage: creer_tableau_suivi.sh <organisation-ou-utilisateur>}"
TITRE="PharmApp — Route vers la production"

echo "Création du projet « $TITRE » pour $PROPRIETAIRE…"
NUMERO="$(gh project create --owner "$PROPRIETAIRE" --title "$TITRE" --format json -q .number)"

ajouter() { # $1 = titre de l'étape, $2 = critère de sortie
  gh project item-create "$NUMERO" --owner "$PROPRIETAIRE" \
    --title "$1" --body "Critère de sortie : $2"
}

ajouter "00 — Gel, unification et gouvernance"        "Un dépôt, une version, aucun document de statut contradictoire"
ajouter "01 — CI durcie et tests au vert"             "100 % des tests verts sur environnement propre, couverture >= 85 %"
ajouter "02 — Intégrité des données"                  "Contraintes et migrations garantissent l'impossibilité d'un état incohérent"
ajouter "03 — Complétude fonctionnelle Phase 1"       "Tous les parcours du cahier des charges exécutables de bout en bout"
ajouter "04 — Intégration matérielle"                 "Vente servie avec scanner et ticket ESC/POS imprimé"
ajouter "05 — Durcissement du poste client"           "Écrans découpés, tests composants et E2E verts"
ajouter "06 — Résilience hors-ligne"                  "8 h de coupure sans perte de vente, reprise automatique"
ajouter "07 — Audit de sécurité OWASP ASVS L2"        "Aucune vulnérabilité haute ou critique ouverte"
ajouter "08 — Épreuve de la synchronisation cloud"    "Convergence garantie et conflits résolus de façon déterministe"
ajouter "09 — Sauvegarde, restauration, supervision"  "Restauration complète chronométrée sous le seuil défini"
ajouter "10 — Industrialisation du déploiement"       "Installation complète réalisée par un non-développeur"
ajouter "11 — Performance"                            "Budgets de latence respectés sur le matériel cible"
ajouter "12 — Recette en conditions d'officine"       "Scénarios métier validés par le pharmacien référent"
ajouter "13 — Conformité réglementaire"               "Registres et obligations légales validés par le titulaire"
ajouter "14 — Déploiement pilote"                     "4 semaines d'exploitation réelle sans incident critique"

echo "Tableau créé : https://github.com/orgs/$PROPRIETAIRE/projects/$NUMERO"
