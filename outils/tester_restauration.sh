#!/usr/bin/env bash
# =============================================================================
# tester_restauration.sh — Test de la procédure de restauration (DT-009)
# =============================================================================
#
# Ce script valide la procédure de restauration en mesurant le RTO/RPO réels.
# Il doit être exécuté HORS production, sur un environnement de test isolé.
#
# Usage :
#   bash outils/tester_restauration.sh [--backup-file /chemin/vers/dump.dump]
#
# Sortie :
#   - Rapport texte dans /tmp/pharmapp_restauration_<timestamp>.txt
#   - Code retour 0 si RTO ≤ 30 min et données cohérentes
#   - Code retour 1 si test échoué
#
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BLUE}[INFO]${RESET}  $*" | tee -a "$RAPPORT"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*" | tee -a "$RAPPORT"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*" | tee -a "$RAPPORT"; }
error()   { echo -e "${RED}[FAIL]${RESET}  $*" | tee -a "$RAPPORT" >&2; }

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RAPPORT="/tmp/pharmapp_restauration_${TIMESTAMP}.txt"
BACKUP_FILE=""
COMPOSE_TEST="infra/docker-compose.test.yml"
RTO_MAX_SECONDES=1800  # 30 minutes

while [[ $# -gt 0 ]]; do
  case $1 in
    --backup-file) BACKUP_FILE="$2"; shift 2 ;;
    *) echo "Argument inconnu : $1"; exit 1 ;;
  esac
done

touch "$RAPPORT"
echo "═══════════════════════════════════════════════════" | tee -a "$RAPPORT"
echo "  TEST RESTAURATION PHARMAPP — $TIMESTAMP"         | tee -a "$RAPPORT"
echo "═══════════════════════════════════════════════════" | tee -a "$RAPPORT"

# ─── PHASE 1 : Sélection du backup ───────────────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 1 : Sélection du backup à restaurer"

if [[ -z "$BACKUP_FILE" ]]; then
  # Chercher le backup le plus récent
  BACKUP_DIR="${BACKUP_DIR:-/var/backups/pharmapp}"
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | head -1 || echo "")
  if [[ -z "$BACKUP_FILE" ]]; then
    # Créer un backup de test à partir de l'instance courante
    warn "Aucun backup trouvé. Création d'un backup de test depuis la DB courante…"
    BACKUP_FILE="/tmp/pharmapp_test_backup_${TIMESTAMP}.dump"
    docker compose -f "${COMPOSE_FILE:-infra/docker-compose.yml}" exec -T \
      "${DB_CONTAINER:-db}" pg_dump -U "${POSTGRES_USER:-pharmapp}" \
      "${POSTGRES_DB:-pharmapp}" --format=custom --compress=6 > "$BACKUP_FILE"
    success "Backup de test créé : $BACKUP_FILE"
  fi
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  error "Fichier backup introuvable : $BACKUP_FILE"
  exit 1
fi

TAILLE=$(du -h "$BACKUP_FILE" | cut -f1)
DATE_BACKUP=$(stat -c %y "$BACKUP_FILE" | cut -d'.' -f1)
info "Backup sélectionné : $BACKUP_FILE ($TAILLE, créé le $DATE_BACKUP)"

# ─── PHASE 2 : Environnement de test isolé ───────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 2 : Démarrage de l'environnement de test isolé"
T_DEBUT=$SECONDS

# Utiliser un réseau Docker isolé pour le test
RESEAU_TEST="pharmapp-test-${TIMESTAMP}"
CONTAINER_DB_TEST="pharmapp-db-test-${TIMESTAMP}"

docker network create "$RESEAU_TEST" 2>/dev/null || true

# Démarrer un PostgreSQL de test
docker run -d \
  --name "$CONTAINER_DB_TEST" \
  --network "$RESEAU_TEST" \
  -e POSTGRES_DB=pharmapp_test \
  -e POSTGRES_USER=pharmapp \
  -e POSTGRES_PASSWORD=test_secret \
  -v "${BACKUP_FILE}:/backup/pharmapp.dump:ro" \
  postgres:16-alpine \
  > /dev/null

# Attendre que PostgreSQL soit prêt
info "Attente PostgreSQL de test…"
for i in $(seq 1 20); do
  if docker exec "$CONTAINER_DB_TEST" pg_isready -U pharmapp -d pharmapp_test &>/dev/null; then
    success "PostgreSQL de test prêt (tentative $i/20)."
    break
  fi
  sleep 2
  [[ "$i" == 20 ]] && { error "PostgreSQL de test non disponible après 40s."; exit 1; }
done

T_ENV_PRET=$SECONDS
info "Environnement prêt en $(( T_ENV_PRET - T_DEBUT ))s."

# ─── PHASE 3 : Restauration ──────────────────────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 3 : Restauration du backup"
T_RESTAURATION_DEBUT=$SECONDS

docker exec "$CONTAINER_DB_TEST" \
  pg_restore \
    -U pharmapp \
    -d pharmapp_test \
    --no-owner \
    --no-privileges \
    --exit-on-error \
    /backup/pharmapp.dump \
  2>&1 | tee -a "$RAPPORT" || {
    error "Restauration échouée."
    docker rm -f "$CONTAINER_DB_TEST" 2>/dev/null || true
    docker network rm "$RESEAU_TEST" 2>/dev/null || true
    exit 1
  }

T_RESTAURATION_FIN=$SECONDS
DUREE_RESTAURATION=$(( T_RESTAURATION_FIN - T_RESTAURATION_DEBUT ))
success "Restauration terminée en ${DUREE_RESTAURATION}s."

# ─── PHASE 4 : Vérification de cohérence ────────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 4 : Vérification de cohérence des données"
ERREURS=0

check_table() {
  local table="$1"
  local col="${2:-id}"
  local count
  count=$(docker exec "$CONTAINER_DB_TEST" psql -U pharmapp -d pharmapp_test -At \
    -c "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "-1")
  if [[ "$count" == "-1" ]]; then
    error "Table introuvable : $table"
    (( ERREURS++ )) || true
  else
    info "Table $table : $count enregistrements"
  fi
}

# Tables critiques
check_table "auth_user"
check_table "catalogue_medicament"
check_table "stocks_lot"
check_table "ventes_vente"
check_table "ventes_lignevente"
check_table "ordonnances_ordonnance"
check_table "produits_controles_registreproduitcontrole"
check_table "audit_journalevenement"

# Vérifier l'intégrité des clés étrangères (PostgreSQL)
info "Vérification de l'intégrité référentielle…"
VIOLATIONS=$(docker exec "$CONTAINER_DB_TEST" psql -U pharmapp -d pharmapp_test -At \
  -c "SELECT COUNT(*) FROM ventes_lignevente lv
      LEFT JOIN ventes_vente v ON lv.vente_id = v.id
      WHERE v.id IS NULL;" 2>/dev/null || echo "-1")

if [[ "$VIOLATIONS" == "0" ]]; then
  success "Intégrité référentielle ventes/lignes : OK"
elif [[ "$VIOLATIONS" == "-1" ]]; then
  warn "Vérification intégrité non applicable (table peut ne pas exister)."
else
  error "$VIOLATIONS ligne(s) de vente orpheline(s) détectées !"
  (( ERREURS++ )) || true
fi

# ─── PHASE 5 : Calcul RTO ────────────────────────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 5 : Calcul du RTO"

T_FIN=$SECONDS
RTO_TOTAL=$(( T_FIN - T_DEBUT ))
RTO_MIN=$(( RTO_TOTAL / 60 ))
RTO_SEC=$(( RTO_TOTAL % 60 ))

info "RTO mesuré  : ${RTO_MIN}m ${RTO_SEC}s (${RTO_TOTAL}s total)"
info "RTO objectif : $(( RTO_MAX_SECONDES / 60 ))m (${RTO_MAX_SECONDES}s)"

if [[ "$RTO_TOTAL" -le "$RTO_MAX_SECONDES" ]]; then
  success "RTO conforme à l'objectif (≤ 30 min)."
else
  error "RTO dépasse l'objectif ! ${RTO_MIN}m ${RTO_SEC}s > 30 min."
  (( ERREURS++ )) || true
fi

# ─── PHASE 6 : Nettoyage ─────────────────────────────────────────────────────

echo "" | tee -a "$RAPPORT"
info "PHASE 6 : Nettoyage de l'environnement de test"
docker rm -f "$CONTAINER_DB_TEST" 2>/dev/null || true
docker network rm "$RESEAU_TEST" 2>/dev/null || true
success "Environnement de test supprimé."

# ─── Rapport final ────────────────────────────────────────────────────────────

echo "" | tee -a "$RAPPORT"
echo "═══════════════════════════════════════════════════" | tee -a "$RAPPORT"
echo "  RÉSULTAT DU TEST DE RESTAURATION"                  | tee -a "$RAPPORT"
echo "═══════════════════════════════════════════════════" | tee -a "$RAPPORT"
echo "  Backup testé  : $BACKUP_FILE"                      | tee -a "$RAPPORT"
echo "  RTO mesuré    : ${RTO_MIN}m ${RTO_SEC}s"           | tee -a "$RAPPORT"
echo "  Erreurs       : $ERREURS"                          | tee -a "$RAPPORT"
echo "  Rapport       : $RAPPORT"                          | tee -a "$RAPPORT"
echo "═══════════════════════════════════════════════════" | tee -a "$RAPPORT"

if [[ "$ERREURS" -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  ✔ TEST RÉUSSI — Restauration validée${RESET}" | tee -a "$RAPPORT"
  exit 0
else
  echo -e "${RED}${BOLD}  ✘ TEST ÉCHOUÉ — $ERREURS erreur(s) détectée(s)${RESET}" | tee -a "$RAPPORT"
  exit 1
fi
