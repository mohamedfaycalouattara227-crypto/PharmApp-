"""
conftest.py (racine) — Configuration pytest globale pour PharmApp.
Configure Django avec une base SQLite en mémoire pour les tests.

IMPORTANT : La configuration Django est faite AU NIVEAU MODULE (pas dans un hook)
pour s'assurer qu'elle s'exécute avant le chargement des conftest enfants.
"""

import django
from datetime import timedelta
from django.conf import settings


# ── Configuration Django immédiate (niveau module) ────────────────────────────
# Doit être fait ici, pas dans pytest_configure, car tests/conftest.py importe
# rest_framework au niveau module et a besoin que Django soit déjà configuré.

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="test-secret-key-pharmapp-non-utiliser-en-production",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "django.contrib.admin",
            "django.contrib.sessions",
            "django.contrib.messages",
            # Apps PharmApp
            "gestion.authentification",
            "gestion.catalogue",
            "gestion.clients",
            "gestion.ventes",
            "gestion.stocks",
            "gestion.ordonnances",
            "gestion.audit",
            "gestion.synchronisation",
            "gestion.comptabilite",
            "gestion.rapports",
            "gestion.produits_controles",
            "gestion.fournisseurs",
            "gestion.parametrage",
            "infrastructure.outbox",
            # Tiers
            "rest_framework",
            # Blacklist des refresh tokens : indispensable pour reproduire en
            # test le comportement de production (rotation + révocation).
            "rest_framework_simplejwt.token_blacklist",
        ],
        AUTH_USER_MODEL="authentification.UtilisateurPharmacien",
        # Même backend qu'en production : c'est lui qui porte le comptage des
        # échecs et le verrouillage de compte (anti-brute-force, DT-015).
        AUTHENTICATION_BACKENDS=["gestion.authentification.backend.BackendPharmApp"],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        TIME_ZONE="Africa/Ouagadougou",
        LANGUAGE_CODE="fr-bf",
        # Celery : mode synchrone en tests (pas de broker requis)
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="cache+memory://",
        # Paramètres métier
        DELAI_ANNULATION_VENTE_MINUTES=30,
        TENTATIVES_CONNEXION_MAX=5,
        DUREE_BLOCAGE_COMPTE_MINUTES=30,
        # Clé de chiffrement des ordonnances (32 octets exactement)
        ORDONNANCE_ENCRYPTION_KEY="test-key-32-bytes-pharmapp-test!",
        ORDONNANCE_MAX_SIZE_MB=5,
        ROOT_URLCONF="pharmapp.urls",
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
        ],
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework_simplejwt.authentication.JWTAuthentication",
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "api.permissions.EstAuthentifie",
            ],
            "DEFAULT_PAGINATION_CLASS": "api.pagination.PaginateurStandard",
            "PAGE_SIZE": 25,
            "EXCEPTION_HANDLER": "api.exceptions_handler.gerer_exception",
            # Limitation de débit désactivée en test : les scénarios de
            # sécurité enchaînent volontairement des dizaines de requêtes et
            # doivent observer le code métier (401/403), pas un 429 d'infra.
            # Les quotas réels restent définis dans pharmapp/settings.py.
            "DEFAULT_THROTTLE_CLASSES": [],
            "DEFAULT_THROTTLE_RATES": {
                "anon": None,
                "user": None,
                "connexion": None,
                "vente": None,
                "ajustement_stock": None,
                "rapport": None,
            },
        },
        SIMPLE_JWT={
            "AUTH_HEADER_TYPES": ("Bearer",),
            "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
            "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": True,
            "UPDATE_LAST_LOGIN": True,
        },
        # Couverture cloud (synchronisation) — désactivé en tests
        CLOUD_API_URL="http://testserver-cloud/",
        CLOUD_API_KEY="test-cloud-key",
        SYNC_BATCH_SIZE=50,
        SYNC_MAX_RETRY=3,
        # Logging silencieux en tests
        LOGGING={
            "version": 1,
            "disable_existing_loggers": True,
            "handlers": {"null": {"class": "logging.NullHandler"}},
            "root": {"handlers": ["null"]},
        },
    )
    django.setup()


def pytest_configure(config):
    """Hook de configuration pytest — Django est déjà configuré au niveau module."""
    pass
