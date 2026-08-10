# Install-PharmApp.ps1
# Installateur PharmApp pour Windows 10/11 (DT-010)
# Exécution : PowerShell -ExecutionPolicy Bypass -File Install-PharmApp.ps1
#
# Ce script :
#   1. Vérifie que Docker Desktop est installé et en cours d'exécution
#   2. Crée les répertoires de données
#   3. Génère les secrets sécurisés (.env)
#   4. Lance les services via Docker Compose
#   5. Ouvre PharmApp dans le navigateur par défaut

#Requires -RunAsAdministrator

param(
    [string]$Domaine   = "localhost",
    [switch]$NoSSL,
    [string]$InstallDir = "$env:ProgramFiles\PharmApp"
)

$ErrorActionPreference = "Stop"

# ─── Fonctions utilitaires ────────────────────────────────────────────────────

function Write-Step  { param([string]$Msg) Write-Host "`n▶ $Msg" -ForegroundColor Cyan -NoNewline; Write-Host "" }
function Write-OK    { param([string]$Msg) Write-Host "  ✔ $Msg" -ForegroundColor Green }
function Write-Info  { param([string]$Msg) Write-Host "  ℹ $Msg" -ForegroundColor White }
function Write-Warn  { param([string]$Msg) Write-Host "  ⚠ $Msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$Msg) Write-Host "  ✘ $Msg" -ForegroundColor Red; exit 1 }

function New-SecureToken {
    param([int]$Bytes = 32)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] $Bytes
    $rng.GetBytes($buf)
    return [Convert]::ToBase64String($buf) -replace '[+/=]', { @{'+' = '-'; '/' = '_'; '=' = ''}[$_.Value] }
}

# ─── Étape 1 : Vérifier Docker Desktop ───────────────────────────────────────

Write-Step "Vérification de Docker Desktop"

try {
    $dockerVersion = docker --version 2>$null
    if (-not $dockerVersion) { throw "Docker non trouvé" }
    Write-OK "Docker trouvé : $dockerVersion"
} catch {
    Write-Fail "Docker Desktop n'est pas installé ou non accessible.`nTéléchargez-le sur : https://www.docker.com/products/docker-desktop/"
}

# Vérifier que le daemon Docker est en cours d'exécution
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop n'est pas démarré. Veuillez le lancer et réessayer."
}
Write-OK "Docker Desktop en cours d'exécution."

# Vérifier Docker Compose v2
try {
    docker compose version 2>$null | Out-Null
    Write-OK "Docker Compose v2 disponible."
} catch {
    Write-Fail "Docker Compose v2 est requis. Mettez à jour Docker Desktop."
}

# ─── Étape 2 : Créer les répertoires ─────────────────────────────────────────

Write-Step "Création des répertoires"

$DataDir   = "$env:ProgramData\PharmApp"
$BackupDir = "$DataDir\backups"

foreach ($dir in @($InstallDir, "$DataDir\postgres", "$DataDir\media", "$DataDir\redis", $BackupDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-OK "Dossier créé : $dir"
    } else {
        Write-Info "Dossier existant : $dir"
    }
}

# ─── Étape 3 : Copier les fichiers Compose ────────────────────────────────────

Write-Step "Copie des fichiers de configuration"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InfraDir  = Join-Path (Split-Path -Parent $ScriptDir) "infra"

if (Test-Path $InfraDir) {
    Copy-Item -Path "$InfraDir\*" -Destination $InstallDir -Recurse -Force
    Write-OK "Fichiers Compose copiés dans $InstallDir"
} else {
    Write-Warn "Dossier infra non trouvé ($InfraDir) — à copier manuellement."
}

# ─── Étape 4 : Générer le fichier .env ───────────────────────────────────────

Write-Step "Génération des secrets"

$EnvFile = "$InstallDir\.env"
if (Test-Path $EnvFile) {
    Write-Warn "Fichier .env existant — secrets conservés."
} else {
    $SecretKey      = New-SecureToken -Bytes 50
    $DbPassword     = New-SecureToken -Bytes 24
    $EncryptionKey  = New-SecureToken -Bytes 32
    $GeneratedDate  = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    $EnvContent = @"
# PharmApp — Fichier d'environnement généré le $GeneratedDate
# CONFIDENTIEL — ne jamais partager ce fichier

DJANGO_SECRET_KEY=$SecretKey
ORDONNANCE_ENCRYPTION_KEY=$EncryptionKey
POSTGRES_DB=pharmapp
POSTGRES_USER=pharmapp
POSTGRES_PASSWORD=$DbPassword
DATABASE_URL=postgresql://pharmapp:${DbPassword}@db:5432/pharmapp
REDIS_URL=redis://redis:6379/0
DJANGO_SETTINGS_MODULE=pharmapp.settings
ALLOWED_HOSTS=$Domaine,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
BACKUP_DIR=$BackupDir
"@
    Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
    # Restreindre les permissions du fichier .env
    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "FullControl", "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $EnvFile -AclObject $acl
    Write-OK "Fichier .env créé avec secrets sécurisés."
}

# ─── Étape 5 : Démarrer les services ─────────────────────────────────────────

Write-Step "Démarrage de PharmApp"

Set-Location $InstallDir
Write-Info "Téléchargement des images Docker (peut prendre quelques minutes)…"
docker compose pull
docker compose up -d

Write-Info "Attente de la disponibilité de l'API…"
$maxTentatives = 20
$ok = $false
for ($i = 1; $i -le $maxTentatives; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/health/" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 3
    Write-Host "  … tentative $i/$maxTentatives" -ForegroundColor DarkGray
}

if (-not $ok) {
    Write-Warn "L'API ne répond pas encore. Vérifiez les logs :"
    Write-Info "  cd '$InstallDir' && docker compose logs serveur"
} else {
    Write-OK "API disponible sur http://localhost:8000"
}

# ─── Étape 6 : Tâche planifiée pour les sauvegardes ──────────────────────────

Write-Step "Configuration des sauvegardes automatiques"

$TaskName = "PharmApp-Backup-Quotidien"
if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    $Action  = New-ScheduledTaskAction -Execute "docker" `
        -Argument "compose -f `"$InstallDir\docker-compose.yml`" exec -T db pg_dump -U pharmapp pharmapp --format=custom --compress=9" `
        -WorkingDirectory $InstallDir
    $Trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
        -Settings $Settings -RunLevel Highest -Force | Out-Null
    Write-OK "Tâche planifiée créée : $TaskName (tous les jours à 02h00)."
} else {
    Write-Info "Tâche planifiée déjà existante : $TaskName"
}

# ─── Résumé ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   PharmApp installé avec succès !            ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Info "Interface web : http://${Domaine}:3000"
Write-Info "API Django    : http://${Domaine}:8000"
Write-Info "Fichier .env  : $EnvFile"
Write-Info "Backups       : $BackupDir"
Write-Info "Logs          : cd '$InstallDir'; docker compose logs -f"
Write-Host ""
Write-Warn "IMPORTANT : Modifiez $EnvFile pour configurer"
Write-Warn "SENTRY_DSN et WEBHOOK_ALERTE_URL selon votre environnement."
Write-Host ""

# Ouvrir PharmApp dans le navigateur
Start-Process "http://localhost:3000"
