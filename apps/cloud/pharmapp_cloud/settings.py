"""
pharmapp_cloud/settings.py
Configuration Django pour le serveur Cloud PharmApp.

Mêmes conventions de durcissement que le backend local (boot-guards prod,
Argon2id, JWT, headers de sécurité) adaptées au contexte multi-tenant cloud.
"""

import os
from pathlib import Path

# ─── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Environnement ────────────────────────────────────────────────────────────
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development")
IS_PROD = DJANGO_ENV == "production"
IS_TEST = DJANGO_ENV == "test"

# ─── Sécurité — clé secrète ───────────────────────────────────────────────────
_SECRET_KEY_DEFAULT = "dev-secret-cloud-key-not-for-production-use-only"
SECRET_KEY = os.environ.get("SECRET_KEY", _SECRET_KEY_DEFAULT)

if IS_PROD:
    if SECRET_KEY == _SECRET_KEY_DEFAULT or len(SECRET_KEY) < 50:
        raise RuntimeError(
            "[CLOUD BOOT] SECRET_KEY absente ou trop courte en production. "
            "Générez-en une via : python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

# ─── Debug ────────────────────────────────────────────────────────────────────
DEBUG = os.environ.get("DEBUG", "True") == "True"

if IS_PROD and DEBUG:
    raise RuntimeError("[CLOUD BOOT] DEBUG=True interdit en production.")

# ─── Hosts autorisés ──────────────────────────────────────────────────────────
_allowed_hosts_raw = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(",") if h.strip()]

if IS_PROD and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise RuntimeError("[CLOUD BOOT] ALLOWED_HOSTS vide ou wildcard interdit en production.")

# ─── Token administrateur cloud ───────────────────────────────────────────────
# Utilisé pour provisionner les officines (endpoint admin uniquement).
_CLOUD_ADMIN_TOKEN_DEFAULT = "dev-admin-token-not-for-production"
CLOUD_ADMIN_TOKEN = os.environ.get("CLOUD_ADMIN_TOKEN", _CLOUD_ADMIN_TOKEN_DEFAULT)

if IS_PROD and CLOUD_ADMIN_TOKEN == _CLOUD_ADMIN_TOKEN_DEFAULT:
    raise RuntimeError(
        "[CLOUD BOOT] CLOUD_ADMIN_TOKEN par défaut interdit en production. "
        "Générez-en un via : python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

# ─── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    # DRF
    "rest_framework",
    # Apps métier cloud
    "apps.identite",
    "apps.synchronisation",
]

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "api.middleware.RequestIdMiddleware",
    "api.middleware.SecurityHeadersMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ─── URLs ─────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "pharmapp_cloud.urls"
WSGI_APPLICATION = "pharmapp_cloud.wsgi.application"

# ─── Base de données ──────────────────────────────────────────────────────────
_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if _DATABASE_URL:
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Dev / test : SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.AuthenticationParCleApi",
        "api.authentication.AuthenticationParTokenAdmin",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        if IS_PROD
        else [
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
        ]
    ),
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
        "ingestion": "1000/minute",   # débit élevé pour les outboxes des pharmacies
        "provisionnement": "10/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "api.exceptions_handler.gestionnaire_exceptions",
}

# ─── Hachage des mots de passe (admin console — Phase 4) ─────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

# ─── Fichiers statiques ───────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Sécurité TLS (prod) ──────────────────────────────────────────────────────
if IS_PROD:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Le cloud n'expose pas de frontend public (Phase 1) — CORS non nécessaire pour l'instant.
# À activer en Phase 4 (console) avec liste stricte d'origines.

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "api.logging.FiltreRequestId",
        },
    },
    "formatters": {
        "json": {
            "()": "api.logging.FormateurJson",
        },
        "console": {
            "format": "[{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if IS_PROD else "console",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "pharmapp_cloud": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "pharmapp_cloud.securite": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ─── Monitoring (Sentry) ──────────────────────────────────────────────────────
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

if SENTRY_DSN and not IS_TEST:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=DJANGO_ENV,
    )
