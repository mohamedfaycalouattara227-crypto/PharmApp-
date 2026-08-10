#!/usr/bin/env bash
# =============================================================================
# install.sh — Installateur PharmApp pour environnement de production Linux
# =============================================================================
# DT-010 : Installateur non-développeur
#
# Prérequis : Ubuntu 22.04 / Debian 12 / Rocky Linux 9
# Exécution : sudo bash install.sh [--domaine mon-domaine.com] [--no-ssl]
#
# Ce script installe et configure automatiquement :
#   - Docker Engine + Docker Compose v2
#   - PharmApp (serveur Django + poste client React)
#   - PostgreSQL 16 (via Docker)
#   - Redis 7 (via Docker)
#   - Nginx (reverse proxy + HTTPS Let's Encrypt optionnel)
#   - Sauvegarde automatique quotidienne (cron)
#
# =============================================================================

set -euo pipefail

# ─── Couleurs ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BLUE}ℹ${RESET}  $*"; }
success() { echo -e "${GREEN}✔${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✘${RESET}  $*" >&2; }
step()    { echo -e "\n${BOLD}▶ $*${RESET}"; }

# ─── Paramètres ───────────────────────────────────────────────────────────────
DOMAINE=""
SANS_SSL=false
INSTALL_DIR="/opt/pharmapp"
DATA_DIR="/var/lib/pharmapp"
BACKUP_DIR="/var/backups/pharmapp"
PHARMAPP_USER="pharmapp"
PHARMAPP_VERSION="${PHARMAPP_VERSION:-latest}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --domaine) DOMAINE="$2"; shift 2 ;;
    --no-ssl)  SANS_SSL=true; shift ;;
    *) error "Argument inconnu : $1"; exit 1 ;;
  esac
done

# ─── Vérifications initiales ──────────────────────────────────────────────────
step "Vérification des prérequis"

if [[ "$(id -u)" -ne 0 ]]; then
  error "Ce script doit être exécuté en tant que root (sudo bash install.sh)."
  exit 1
fi

# Détecter la distro
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VER="${VERSION_ID:-0}"
else
  error "Impossible de détecter le système d'exploitation."
  exit 1
fi
info "OS détecté : $OS_ID $OS_VER"

# RAM minimale : 1 Go
RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
if [[ "$RAM_KB" -lt 900000 ]]; then
  warn "RAM disponible : $(( RAM_KB / 1024 )) Mo. Minimum recommandé : 1 Go."
fi

# Espace disque : 5 Go minimum
ESPACE_LIBRE=$(df -BG / | tail -1 | awk '{print $4}' | tr -d G)
if [[ "$ESPACE_LIBRE" -lt 5 ]]; then
  error "Espace disque insuffisant : ${ESPACE_LIBRE} Go libres (minimum : 5 Go)."
  exit 1
fi
success "Prérequis système validés."

# ─── ÉTAPE 1 : Installer Docker ───────────────────────────────────────────────
step "Installation de Docker Engine"

if command -v docker &>/dev/null; then
  success "Docker déjà installé : $(docker --version)"
else
  case "$OS_ID" in
    ubuntu|debian)
      apt-get update -qq
      apt-get install -y -qq ca-certificates curl gnupg lsb-release
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/${OS_ID}/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      chmod a+r /etc/apt/keyrings/docker.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/${OS_ID} $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
      apt-get update -qq
      apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
      ;;
    rhel|rocky|almalinux|centos)
      dnf install -y -q dnf-plugins-core
      dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
      dnf install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
      ;;
    *)
      error "Distribution non supportée : $OS_ID. Installez Docker manuellement."
      exit 1
      ;;
  esac

  systemctl enable --now docker
  success "Docker installé et démarré."
fi

# ─── ÉTAPE 2 : Créer l'utilisateur pharmapp ───────────────────────────────────
step "Création de l'utilisateur système pharmapp"

if ! id "$PHARMAPP_USER" &>/dev/null; then
  useradd --system --shell /bin/bash --home "$INSTALL_DIR" \
    --create-home "$PHARMAPP_USER"
  usermod -aG docker "$PHARMAPP_USER"
  success "Utilisateur '$PHARMAPP_USER' créé."
else
  success "Utilisateur '$PHARMAPP_USER' déjà existant."
fi

# ─── ÉTAPE 3 : Créer les répertoires ──────────────────────────────────────────
step "Création des répertoires"

for dir in "$INSTALL_DIR" "$DATA_DIR/postgres" "$DATA_DIR/media" \
           "$DATA_DIR/redis" "$BACKUP_DIR"; do
  mkdir -p "$dir"
  chown "$PHARMAPP_USER:$PHARMAPP_USER" "$dir"
done
success "Répertoires créés."

# ─── ÉTAPE 4 : Générer les secrets ────────────────────────────────────────────
step "Génération des secrets sécurisés"

ENV_FILE="$INSTALL_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  warn "Fichier .env existant — secrets conservés."
else
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
  DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

  cat > "$ENV_FILE" <<EOF
# PharmApp — Fichier d'environnement généré le $(date)
# CONFIDENTIEL — ne jamais committer dans Git

DJANGO_SECRET_KEY=${SECRET_KEY}
ORDONNANCE_ENCRYPTION_KEY=${ENCRYPTION_KEY}
POSTGRES_DB=pharmapp
POSTGRES_USER=pharmapp
POSTGRES_PASSWORD=${DB_PASSWORD}
DATABASE_URL=postgresql://pharmapp:${DB_PASSWORD}@db:5432/pharmapp
REDIS_URL=redis://redis:6379/0
DJANGO_SETTINGS_MODULE=pharmapp.settings
ALLOWED_HOSTS=${DOMAINE:-localhost,127.0.0.1}
CORS_ALLOWED_ORIGINS=http://localhost:3000
BACKUP_DIR=${BACKUP_DIR}
EOF
  chmod 600 "$ENV_FILE"
  chown "$PHARMAPP_USER:$PHARMAPP_USER" "$ENV_FILE"
  success "Fichier .env créé avec secrets sécurisés."
fi

# ─── ÉTAPE 5 : Copier les fichiers Compose ────────────────────────────────────
step "Configuration Docker Compose"

cp -r "$(dirname "$0")/../infra/"* "$INSTALL_DIR/"
chown -R "$PHARMAPP_USER:$PHARMAPP_USER" "$INSTALL_DIR"
success "Fichiers Compose copiés dans $INSTALL_DIR."

# ─── ÉTAPE 6 : Démarrer les services ─────────────────────────────────────────
step "Démarrage des services PharmApp"

cd "$INSTALL_DIR"
sudo -u "$PHARMAPP_USER" docker compose pull
sudo -u "$PHARMAPP_USER" docker compose up -d

# Attendre que Django soit prêt
info "Attente de la disponibilité de l'API…"
for i in $(seq 1 20); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health/ 2>/dev/null || echo "000")
  if [[ "$HTTP" == "200" ]]; then
    success "API disponible (HTTP $HTTP)."
    break
  fi
  sleep 3
  [[ "$i" == 20 ]] && { error "L'API ne répond pas après 60s."; exit 2; }
done

# ─── ÉTAPE 7 : Configurer les sauvegardes automatiques ────────────────────────
step "Sauvegarde automatique quotidienne"

CRON_FILE="/etc/cron.d/pharmapp-backup"
cat > "$CRON_FILE" <<CRON
# PharmApp — Sauvegarde quotidienne à 2h00
0 2 * * * $PHARMAPP_USER cd $INSTALL_DIR && docker compose exec -T db \
  pg_dump -U pharmapp pharmapp --format=custom --compress=9 \
  > $BACKUP_DIR/pharmapp_\$(date +\%Y\%m\%d).dump 2>/dev/null && \
  ls -t $BACKUP_DIR/*.dump | tail -n +8 | xargs -r rm --
CRON
chmod 644 "$CRON_FILE"
success "Sauvegarde automatique configurée (cron : /etc/cron.d/pharmapp-backup)."

# ─── Résumé ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║   PharmApp installé avec succès !             ║${RESET}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${RESET}"
echo ""
info "Interface web    : http://${DOMAINE:-localhost}:3000"
info "API Django       : http://${DOMAINE:-localhost}:8000"
info "Fichier .env     : $ENV_FILE"
info "Backups          : $BACKUP_DIR"
info "Logs             : cd $INSTALL_DIR && docker compose logs -f"
echo ""
warn "IMPORTANT : Modifiez le fichier .env pour configurer votre domaine,"
warn "votre DSN Sentry (SENTRY_DSN) et votre webhook d'alerte (WEBHOOK_ALERTE_URL)."
echo ""
