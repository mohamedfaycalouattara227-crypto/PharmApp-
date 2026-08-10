"""
conftest.py — Configuration pytest globale pour pharmapp_cloud.

Utilise SQLite en mémoire pour des tests rapides et isolés.
Celery en mode eager (synchrone) — aucun worker requis.
"""

import django
from django.conf import settings


def pytest_configure(config):
    settings.configure(
        DJANGO_ENV="test",
        DEBUG=False,
        SECRET_KEY="test-secret-key-pharmapp-cloud-only-for-testing",
        CLOUD_ADMIN_TOKEN="test-admin-token-only-for-testing",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "rest_framework",
            "apps.identite",
            "apps.synchronisation",
        ],
        ROOT_URLCONF="pharmapp_cloud.urls",
        LANGUAGE_CODE="fr-fr",
        TIME_ZONE="Africa/Ouagadougou",
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "api.authentication.AuthenticationParCleApi",
                "api.authentication.AuthenticationParTokenAdmin",
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated",
            ],
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
            ],
            "DEFAULT_THROTTLE_CLASSES": [],
            "DEFAULT_THROTTLE_RATES": {
                "ingestion":      "10000/minute",   # élevé pour les tests
                "provisionnement": "10000/minute",
            },
            "EXCEPTION_HANDLER": "api.exceptions_handler.gestionnaire_exceptions",
        },
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "api.middleware.RequestIdMiddleware",
            "api.middleware.SecurityHeadersMiddleware",
            "django.middleware.common.CommonMiddleware",
        ],
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "null": {"class": "logging.NullHandler"},
            },
            "root": {"handlers": ["null"]},
        },
    )
