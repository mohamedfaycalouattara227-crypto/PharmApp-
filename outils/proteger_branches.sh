#!/usr/bin/env bash
# outils/proteger_branches.sh — Applique la protection de `main` (règles G-04 à G-06).
# Nécessite la CLI GitHub `gh` authentifiée avec les droits d'administration.
set -euo pipefail

DEPOT="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Protection de main sur $DEPOT…"

gh api -X PUT "repos/$DEPOT/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  -F "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=lint" \
  -f "required_status_checks[contexts][]=types" \
  -f "required_status_checks[contexts][]=tests-serveur" \
  -f "required_status_checks[contexts][]=tests-client" \
  -f "required_status_checks[contexts][]=securite" \
  -f "required_status_checks[contexts][]=gouvernance" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  -F "required_pull_request_reviews[require_last_push_approval]=true" \
  -F "required_conversation_resolution=true" \
  -F "required_linear_history=true" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false" \
  -F "restrictions=null"

echo "Protection appliquée : PR obligatoire, 1 revue, CI verte, historique linéaire."
