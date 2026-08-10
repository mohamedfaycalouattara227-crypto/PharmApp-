"""
pharmapp/settings.py — Configuration Django de PharmApp.

Version durcie (audit OWASP ASVS L2 / Top 10 2021).
Voir docs/AUDIT_OWASP_ASVS_L2.md pour le rapport complet.
"""

import os
import base64
from pathlib import Path
from datetime import timedelta

# ─── Utilitaires ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").lower()
IS_PROD = DJANGO_ENV == "production"
IS_TEST = DJANGO_ENV == "test" or os.environ.get("TESTING") == "1"


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _require_env(key: str, fallback: str | None = None) -> str:
    val = os.environ.get(key, fallback)
    if val is None:
        raise RuntimeError(
            f"Variable d'environnement obligatoire absente : {key}. "
            "Vérifiez votre fichier .env ou les variables d'env du déploiement."
        )
    return val


# ─── Sécurité de base ─────────────────────────────────────────────────────────

_DEV_SECRET = "pharmapp-dev-secret-key-not-for-production"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET)

if IS_PROD and SECRET_KEY == _DEV_SECRET:
    raise RuntimeError("SECRET_KEY doit être définie en production.")
# ASVS V6.2.4 : entropie minimale (approx. 256 bits ~= 43 chars b64)
if IS_PROD and len(SECRET_KEY) < 50:
    raise RuntimeError("SECRET_KEY trop courte (>= 50 caractères requis en production).")

DEBUG = _env_bool("DEBUG", default=not IS_PROD)
if IS_PROD and DEBUG:
    raise RuntimeError("DEBUG=True est interdit en production (fuite d'informations).")

ALLOWED_HOSTS_RAW = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_RAW.split(",") if h.strip()]
if IS_PROD and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise RuntimeError("ALLOWED_HOSTS doit être défini strictement en production.")

# ─── Applications installées ──────────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
]

LOCAL_APPS = [
    "api",
    "gestion.authentification",
    "gestion.catalogue",
    "gestion.clients",
    "gestion.ventes",
    "gestion.stocks",
    "gestion.ordonnances",
    "gestion.fournisseurs",
    "gestion.rapports",
    "gestion.parametrage",
    "gestion.produits_controles",
    "gestion.synchronisation",
    "gestion.comptabilite",
    "gestion.audit",
    "infrastructure.outbox",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ───────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",           # ASVS V14.4 : servir statiques compressés & headers cache
    "api.middleware.RequestIdMiddleware",
    "api.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pharmapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pharmapp.wsgi.application"
AUTH_USER_MODEL = "authentification.UtilisateurPharmacien"
# CORRECTIF (audit 2026-07-21) : le chemin pointait vers "api.authentication",
# module qui ne définit QUE JWTCookieAuthentication — BackendPharmApp est en
# réalité dans gestion.authentification.backend. L'ancien chemin provoquait un
# AttributeError non intercepté par Django à chaque appel de authenticate(),
# donc un plantage systématique de toute tentative de connexion en production.
# Non détecté par la suite de tests car conftest.py configure Django via
# settings.configure() sans jamais charger ce module.
AUTHENTICATION_BACKENDS = ["gestion.authentification.backend.BackendPharmApp"]

# ─── Base de données ──────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(
            DATABASE_URL,
            conn_max_age=60,
            ssl_require=IS_PROD,
            conn_health_checks=True,  # ASVS V1.11 : détecter connexions cassées avant requête
        )
    }
elif IS_PROD:
    raise RuntimeError("DATABASE_URL (postgres) est obligatoire en production.")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ─── Mots de passe (ASVS V2.1) ────────────────────────────────────────────────
# Argon2id en premier → hash par défaut pour les nouveaux mots de passe.
# PBKDF2 conservé en second → rehash transparent des anciens mots de passe.

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # ASVS V2.1.1 : longueur minimale 12 caractères
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ─────────────────────────────────────────────────────

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

# ─── Fichiers statiques & médias ──────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# WhiteNoise : manifest immuable + compression
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── REST Framework ───────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.JWTCookieAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "api.permissions.EstAuthentifie",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",  # CORRECTIF : les throttles UserRateThrottle scopés étaient ignorés
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "200/min",
        "connexion": "5/min",
        "vente": "60/min",
        "ajustement_stock": "30/min",
        "rapport": "10/min",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "api.exceptions_handler.gerer_exception",
    # ASVS V13.2.1 : refuser navigation d'API en prod
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        if IS_PROD else
        ["rest_framework.renderers.JSONRenderer",
         "rest_framework.renderers.BrowsableAPIRenderer"]
    ),
}

# ─── Simple JWT ───────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    # ASVS V3.3 : accès court, refresh rotatif + blacklist
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# ─── CORS ─────────────────────────────────────────────────────────────────────

_CORS_ORIGINS_RAW = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
CORS_ALLOWED_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # explicite
if IS_PROD and any(o.startswith("http://") and "localhost" not in o for o in CORS_ALLOWED_ORIGINS):
    raise RuntimeError("CORS_ALLOWED_ORIGINS ne doit contenir que des origines HTTPS en production.")

# ─── CSRF (ASVS V4.2) ────────────────────────────────────────────────────────

_CSRF_TRUSTED_RAW = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _CSRF_TRUSTED_RAW.split(",") if o.strip()] or CORS_ALLOWED_ORIGINS

CSRF_COOKIE_NAME = "pharmapp_csrf"
CSRF_HEADER_NAME = "HTTP_X_CSRF_TOKEN"
CSRF_COOKIE_HTTPONLY = False  # requis par le double-submit
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = IS_PROD

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = IS_PROD
SESSION_COOKIE_SAMESITE = "Strict"  # aligné sur CSRF (était Lax)
SESSION_COOKIE_AGE = 60 * 60 * 8    # 8h max
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ─── Chiffrement ordonnances (ASVS V6.2) ─────────────────────────────────────
# La clé DOIT être une base64 urlsafe de 32 octets (format Fernet).

_DEV_ORDONNANCE_KEY = base64.urlsafe_b64encode(b"dev-key-non-securise-32-bytes!!!").decode()

def _valider_cle_fernet(cle: str) -> str:
    """Vérifie la conformité stricte au format Fernet (44 chars base64url)."""
    try:
        raw = base64.urlsafe_b64decode(cle.encode())
    except Exception as exc:
        raise RuntimeError(f"ORDONNANCE_ENCRYPTION_KEY invalide (base64url attendu) : {exc}") from exc
    if len(raw) != 32:
        raise RuntimeError("ORDONNANCE_ENCRYPTION_KEY doit décoder à exactement 32 octets.")
    return cle

if IS_PROD:
    ORDONNANCE_ENCRYPTION_KEY = _valider_cle_fernet(_require_env("ORDONNANCE_ENCRYPTION_KEY"))
    if ORDONNANCE_ENCRYPTION_KEY == _DEV_ORDONNANCE_KEY:
        raise RuntimeError("ORDONNANCE_ENCRYPTION_KEY doit être régénérée en production.")
else:
    ORDONNANCE_ENCRYPTION_KEY = os.environ.get("ORDONNANCE_ENCRYPTION_KEY", _DEV_ORDONNANCE_KEY)
    try:
        _valider_cle_fernet(ORDONNANCE_ENCRYPTION_KEY)
    except RuntimeError:
        ORDONNANCE_ENCRYPTION_KEY = _DEV_ORDONNANCE_KEY

# ─── Métier — Ventes / Sécurité fonctionnelle ────────────────────────────────

DELAI_ANNULATION_VENTE_MINUTES = int(os.environ.get("DELAI_ANNULATION_VENTE_MINUTES", "30"))
AUDIT_RETENTION_JOURS = int(os.environ.get("AUDIT_RETENTION_JOURS", "3650"))
TENTATIVES_CONNEXION_MAX = int(os.environ.get("TENTATIVES_CONNEXION_MAX", "5"))
DUREE_BLOCAGE_COMPTE_MINUTES = int(os.environ.get("DUREE_BLOCAGE_COMPTE_MINUTES", "30"))
INACTIVITE_TIMEOUT_MINUTES = int(os.environ.get("INACTIVITE_TIMEOUT_MINUTES", "15"))

# ─── Supabase (optionnel) ─────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if IS_PROD and not SUPABASE_URL:
    import warnings
    warnings.warn(
        "SUPABASE_URL non configurée : la synchronisation cloud est désactivée.",
        RuntimeWarning, stacklevel=2,
    )

# ─── Sécurité HTTP (ASVS V14.4) ──────────────────────────────────────────────

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if IS_PROD:
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0

# ─── Celery ───────────────────────────────────────────────────────────────────

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_ALWAYS_EAGER", IS_TEST)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True   # ASVS V1.11 : pas de perte silencieuse
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000   # éviter fuites mémoire
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

if IS_PROD and CELERY_BROKER_URL.startswith("rediss://"):
    import ssl as _ssl
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": _ssl.CERT_REQUIRED}
    CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL

# ─── Sauvegardes locales ─────────────────────────────────────────────────────

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")
BACKUP_RETENTION_JOURS = int(os.environ.get("BACKUP_RETENTION_JOURS", "7"))

# ─── Médias & Upload (ASVS V12.1) ────────────────────────────────────────────

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# ─── Logging (ASVS V7) ───────────────────────────────────────────────────────
# Rotation automatique + injection du request_id + logs JSON en prod.

_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "api.middleware.RequestIdFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} rid={request_id} {module} {message}",
            "style": "{",
        },
        "json": {
            "()": "pharmapp.log_formatter.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if IS_PROD else "verbose",
            "filters": ["request_id"],
        },
        "fichier_securite": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "securite.log"),
            "maxBytes": 10 * 1024 * 1024,   # 10 Mo
            "backupCount": 20,               # ~200 Mo max, ASVS V7.1.1 rétention
            "formatter": "json" if IS_PROD else "verbose",
            "filters": ["request_id"],
            "delay": True,
        },
    },
    "loggers": {
        "pharmapp":            {"handlers": ["console"],                          "level": "INFO" if not DEBUG else "DEBUG", "propagate": False},
        "pharmapp.securite":   {"handlers": ["console", "fichier_securite"],     "level": "WARNING", "propagate": False},
        "pharmapp.auth":       {"handlers": ["console", "fichier_securite"],     "level": "INFO",    "propagate": False},
        "pharmapp.audit":      {"handlers": ["console", "fichier_securite"],     "level": "INFO",    "propagate": False},
        "django.security":     {"handlers": ["console", "fichier_securite"],     "level": "WARNING", "propagate": False},
        "django.request":      {"handlers": ["console", "fichier_securite"],     "level": "WARNING", "propagate": False},
    },
}

# ─── Sentry (optionnel) ──────────────────────────────────────────────────────

_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN and not IS_TEST:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        import logging as _logging

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.environ.get("SENTRY_ENVIRONMENT", DJANGO_ENV),
            integrations=[
                DjangoIntegration(),
                CeleryIntegration(),
                LoggingIntegration(level=_logging.INFO, event_level=_logging.ERROR),
            ],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
        )
    except ImportError:
        pass
