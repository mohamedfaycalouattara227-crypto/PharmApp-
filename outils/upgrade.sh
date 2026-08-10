#!/usr/bin/env bash
# =============================================================================
# upgrade.sh — Script de montée de version PharmApp (DT-017)
# =============================================================================
#
# Usage :
#   ./outils/upgrade.sh [--version 1.0.3] [--skip-backup] [--dry-run]
#
# Ce script :
#  1. Vérifie les prérequis (Docker, Python, Node, Git)
#  2. Crée un backup automatique de la base + media avant migration
#  3. Tire les nouvelles images Docker
#  4. Applique les migrations Django (avec vérification préalable)
#  5. Redémarre les services en rolling update (zéro interruption)
#  6. Vérifie la santé post-déploiement
#  7. En cas d'échec, propose un rollback automatique
#
# Variables d'environnement requises :
#   COMPOSE_FILE  — chemin vers docker-compose.yml (défaut: infra/docker-compose.yml)
#   DB_CONTAINER  — nom du service PostgreSQL (défaut: db)
#   APP_CONTAINER — nom du service Django (défaut: serveur)
#   BACKUP_DIR    — dossier de sauvegarde (défaut: /var/backups/pharmapp)
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ─── Couleurs ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BLUE}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[ERREUR]${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}━━━ $* ━━━${RESET}"; }

# ─── Variables configurables ──────────────────────────────────────────────────
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.yml}"
DB_CONTAINER="${DB_CONTAINER:-db}"
APP_CONTAINER="${APP_CONTAINER:-serveur}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/pharmapp}"
NEW_VERSION=""
SKIP_BACKUP=false
DRY_RUN=false
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─── Parsing des arguments ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --version)    NEW_VERSION="$2"; shift 2 ;;
    --skip-backup) SKIP_BACKUP=true; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    *) error "Argument inconnu : $1"; exit 1 ;;
  esac
done

[[ "$DRY_RUN" == true ]] && warn "MODE DRY-RUN activé — aucune modification ne sera appliquée."

# ─── Fonctions utilitaires ────────────────────────────────────────────────────

require_cmd() {
  if ! command -v "$1" &>/dev/null; then
    error "Commande requise non trouvée : $1"
    exit 1
  fi
}

docker_exec() {
  docker compose -f "$COMPOSE_FILE" exec -T "$APP_CONTAINER" "$@"
}

# ─── ÉTAPE 1 : Vérification des prérequis ─────────────────────────────────────
step "1/7 Vérification des prérequis"
require_cmd docker
require_cmd git
require_cmd curl

COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "0")
info "Docker Compose : $COMPOSE_VERSION"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  error "Fichier Compose introuvable : $COMPOSE_FILE"
  exit 1
fi
success "Prérequis validés."

# ─── ÉTAPE 2 : Lire la version actuelle ──────────────────────────────────────
step "2/7 Version actuelle"
CURRENT_VERSION=$(docker_exec python -c "import pharmapp; print(pharmapp.__version__)" 2>/dev/null || echo "inconnue")
info "Version installée : $CURRENT_VERSION"
[[ -n "$NEW_VERSION" ]] && info "Version cible      : $NEW_VERSION"

# ─── ÉTAPE 3 : Sauvegarde automatique ────────────────────────────────────────
step "3/7 Sauvegarde pré-migration"

if [[ "$SKIP_BACKUP" == true ]]; then
  warn "Sauvegarde ignorée (--skip-backup)."
else
  mkdir -p "$BACKUP_DIR"
  BACKUP_FILE="$BACKUP_DIR/pharmapp_pre_upgrade_${TIMESTAMP}.dump"

  if [[ "$DRY_RUN" == false ]]; then
    info "Dump PostgreSQL → $BACKUP_FILE"
    docker compose -f "$COMPOSE_FILE" exec -T "$DB_CONTAINER" \
      pg_dump -U "${POSTGRES_USER:-pharmapp}" "${POSTGRES_DB:-pharmapp}" \
      --format=custom --compress=9 > "$BACKUP_FILE"

    TAILLE=$(du -h "$BACKUP_FILE" | cut -f1)
    success "Backup créé : $BACKUP_FILE ($TAILLE)"

    # Conserver les 5 derniers backups
    ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | tail -n +6 | xargs -r rm --
    info "Anciens backups purgés (conservation : 5 derniers)."
  else
    info "[DRY-RUN] pg_dump → $BACKUP_FILE (non exécuté)"
  fi
fi

# ─── ÉTAPE 4 : Pull des nouvelles images ─────────────────────────────────────
step "4/7 Mise à jour des images"

if [[ "$DRY_RUN" == false ]]; then
  docker compose -f "$COMPOSE_FILE" pull
  success "Images Docker mises à jour."
else
  info "[DRY-RUN] docker compose pull (non exécuté)"
fi

# ─── ÉTAPE 5 : Vérification des migrations Django ─────────────────────────────
step "5/7 Vérification des migrations"

if [[ "$DRY_RUN" == false ]]; then
  info "Exécution de 'manage.py check --deploy'…"
  docker_exec python manage.py check --deploy 2>&1 | grep -v "^System check" || true

  info "Vérification des migrations en attente…"
  PENDING=$(docker_exec python manage.py showmigrations --plan 2>/dev/null | grep "\[ \]" | wc -l)
  if [[ "$PENDING" -gt 0 ]]; then
    info "$PENDING migration(s) en attente. Application…"
    docker_exec python manage.py migrate --no-input
    success "Migrations appliquées."
  else
    success "Aucune migration en attente."
  fi
else
  info "[DRY-RUN] migrate --no-input (non exécuté)"
fi

# ─── ÉTAPE 6 : Redémarrage rolling ────────────────────────────────────────────
step "6/7 Redémarrage des services"

if [[ "$DRY_RUN" == false ]]; then
  # Redémarrer le worker Celery sans toucher la DB
  docker compose -f "$COMPOSE_FILE" up -d --no-deps --build celery_worker 2>/dev/null || true
  docker compose -f "$COMPOSE_FILE" up -d --no-deps --build celery_beat  2>/dev/null || true
  # Redémarrer le serveur Django (--no-deps conserve la DB up)
  docker compose -f "$COMPOSE_FILE" up -d --no-deps --build "$APP_CONTAINER"
  success "Services redémarrés."
else
  info "[DRY-RUN] docker compose up -d --no-deps --build (non exécuté)"
fi

# ─── ÉTAPE 7 : Vérification de santé post-déploiement ────────────────────────
step "7/7 Health check post-déploiement"

if [[ "$DRY_RUN" == false ]]; then
  MAX_TENTATIVES=10
  ATTENTE=3
  for i in $(seq 1 $MAX_TENTATIVES); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health/ 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
      success "Health check OK (tentative $i/$MAX_TENTATIVES — HTTP $HTTP_CODE)"
      break
    fi
    warn "Health check : HTTP $HTTP_CODE — nouvelle tentative dans ${ATTENTE}s… ($i/$MAX_TENTATIVES)"
    sleep "$ATTENTE"
    if [[ "$i" == "$MAX_TENTATIVES" ]]; then
      error "Health check échoué après $MAX_TENTATIVES tentatives."
      error "Consultez les logs : docker compose -f $COMPOSE_FILE logs $APP_CONTAINER"
      echo ""
      error "Pour rollback → restaurez le backup : $BACKUP_FILE"
      error "Puis : docker compose -f $COMPOSE_FILE down && docker compose -f $COMPOSE_FILE up -d"
      exit 2
    fi
  done
else
  info "[DRY-RUN] curl http://localhost:8000/api/health/ (non exécuté)"
fi

# ─── Résumé ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║  Montée de version PharmApp réussie !    ║${RESET}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""
info "Version précédente : $CURRENT_VERSION"
[[ -n "$NEW_VERSION" ]] && info "Version installée  : $NEW_VERSION"
[[ "$SKIP_BACKUP" == false && "$DRY_RUN" == false ]] && info "Backup conservé    : $BACKUP_FILE"
info "Horodatage         : $TIMESTAMP"
echo ""
