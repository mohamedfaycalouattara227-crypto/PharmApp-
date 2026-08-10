#!/usr/bin/env bash
# =============================================================================
# outils/lancer_tests_serveur.sh
#
# Lance la suite complète de tests du serveur local (DT-001).
# Produit : rapport HTML de couverture + rapport JSON pytest pour la CI.
#
# Usage :
#   ./outils/lancer_tests_serveur.sh                  # mode local (SQLite)
#   DATABASE_URL=postgres://... ./outils/lancer_tests_serveur.sh  # Postgres
#
# Prérequis :
#   - Python 3.12+, pip installé
#   - Depuis la racine du monorepo
# =============================================================================

set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$RACINE/apps/serveur-local"
RAPPORTS="$RACINE/rapports-tests"

echo "═══════════════════════════════════════════════════════════════"
echo "  PharmApp — Suite de tests serveur local (DT-001)"
echo "  Répertoire : $BACKEND"
echo "  Date       : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "═══════════════════════════════════════════════════════════════"

# ── 1. Variables d'environnement de test ──────────────────────────────────────
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-pharmapp.settings}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////:memory:}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/1}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-cle-de-test-locale-non-secrete-000000000000000}"
export IS_PROD="${IS_PROD:-False}"
export ORDONNANCE_ENCRYPTION_KEY="${ORDONNANCE_ENCRYPTION_KEY:-}"

mkdir -p "$RAPPORTS"

# ── 2. Installation des dépendances ───────────────────────────────────────────
echo ""
echo "▶  Installation des dépendances Python…"
pip install -q \
    -r "$BACKEND/requirements.txt" \
    -r "$BACKEND/requirements-dev.txt"

# ── 3. Vérification de la configuration Django ────────────────────────────────
echo ""
echo "▶  Vérification de la configuration Django (manage.py check)…"
python "$BACKEND/manage.py" check --deploy 2>/dev/null || \
    python "$BACKEND/manage.py" check  # En mode test, --deploy peut échouer (DEBUG=True)

# ── 4. Lancement des tests avec couverture ────────────────────────────────────
echo ""
echo "▶  Lancement de pytest — tous les tests…"
echo ""

cd "$BACKEND"

# Construire la commande pytest
PYTEST_ARGS=(
    # Couverture
    "--cov=."
    "--cov-report=html:$RAPPORTS/coverage-html"
    "--cov-report=term-missing:skip-covered"
    "--cov-report=json:$RAPPORTS/coverage.json"
    "--cov-fail-under=85"  # Seuil cible étape 01

    # Rapport JSON pour la CI
    "--json-report"
    "--json-report-file=$RAPPORTS/pytest-report.json"

    # Affichage
    "--tb=short"
    "--no-header"
    "-q"
    "--maxfail=0"         # Continuer même en cas d'échec pour mesurer le taux réel

    # Marqueurs
    "-m" "not e2e"        # Exclure les tests E2E (ils nécessitent Playwright)
)

set +e  # Ne pas quitter immédiatement en cas d'échec pytest
pytest "${PYTEST_ARGS[@]}"
CODE_RETOUR=$?
set -e

# ── 5. Rapport synthétique ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  RAPPORT DE SYNTHÈSE — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════════════════════════"

if [ -f "$RAPPORTS/coverage.json" ]; then
    TAUX=$(python3 -c "
import json, sys
with open('$RAPPORTS/coverage.json') as f:
    d = json.load(f)
total = d.get('totals', {})
pct = total.get('percent_covered_display', total.get('percent_covered', '?'))
print(f'Couverture globale : {pct}%')
stmts = total.get('num_statements', '?')
missed = total.get('missing_lines', total.get('num_partial_branches', '?'))
print(f'Lignes : {stmts} statements, {missed} non couverts')
" 2>/dev/null || echo "  (impossible de lire coverage.json)")
    echo "  $TAUX"
fi

if [ -f "$RAPPORTS/pytest-report.json" ]; then
    python3 -c "
import json
with open('$RAPPORTS/pytest-report.json') as f:
    d = json.load(f)
summary = d.get('summary', {})
total    = summary.get('total', 0)
passed   = summary.get('passed', 0)
failed   = summary.get('failed', 0)
error    = summary.get('error', 0)
skipped  = summary.get('skipped', 0)
duration = d.get('duration', 0)
print(f'  Tests       : {total} total')
print(f'  Réussis     : {passed}  ({passed*100//total if total else 0}%)')
print(f'  Échoués     : {failed}')
print(f'  Erreurs     : {error}')
print(f'  Ignorés     : {skipped}')
print(f'  Durée       : {duration:.1f}s')
" 2>/dev/null || echo "  (impossible de lire pytest-report.json)"
fi

echo ""
echo "  Rapport HTML de couverture : $RAPPORTS/coverage-html/index.html"
echo "  Rapport JSON pytest        : $RAPPORTS/pytest-report.json"
echo "═══════════════════════════════════════════════════════════════"

if [ $CODE_RETOUR -eq 0 ]; then
    echo "  ✅  TOUS LES TESTS PASSENT — DT-001 potentiellement résolu"
    echo "      (exécuter sur un environnement propre CI pour confirmer)"
else
    echo "  ❌  ÉCHECS DÉTECTÉS — Code de retour : $CODE_RETOUR"
    echo "      Consulter le rapport HTML pour les détails."
    echo "      DT-001 reste OUVERT jusqu'à exécution au vert sur CI."
fi
echo "═══════════════════════════════════════════════════════════════"

exit $CODE_RETOUR
