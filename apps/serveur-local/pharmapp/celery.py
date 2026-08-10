"""
Configuration Celery pour PharmApp.

L'Outbox transactionnelle est traitée par Celery Beat (worker + scheduler).
En environnement de test, CELERY_TASK_ALWAYS_EAGER = True exécute toutes
les tâches de manière synchrone sans broker.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmapp.settings")

app = Celery("pharmapp")

# Charge la configuration Celery depuis Django settings (préfixe CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Découverte automatique des tâches dans tous les modules tasks.py et taches_celery.py
app.autodiscover_tasks([
    "infrastructure",
    "gestion.ventes",
    "gestion.stocks",
    "gestion.clients",
    "gestion.audit",
    "gestion.sync",
])

# Schedule Beat — fréquences de traitement
app.conf.beat_schedule = {
    "outbox-toutes-30s": {
        "task": "infrastructure.taches_celery.traiter_outbox_periodique",
        "schedule": 30.0,
    },
    "connexion-cloud-toutes-60s": {
        "task": "infrastructure.taches_celery.verifier_connexion_cloud",
        "schedule": 60.0,
    },
    "alertes-stock-toutes-15min": {
        "task": "infrastructure.taches_celery.verifier_alertes_stock_periodique",
        "schedule": 900.0,
    },
    "rejouer-echecs-toutes-heures": {
        "task": "infrastructure.taches_celery.rejouer_echecs_automatique",
        "schedule": 3600.0,
    },
    "nettoyage-outbox-quotidien": {
        "task": "infrastructure.taches_celery.nettoyer_outbox_traite",
        "schedule": 86400.0,
    },
    "integrite-audit-quotidien": {
        "task": "infrastructure.taches_celery.verifier_integrite_audit",
        "schedule": 86400.0,
    },
    "reconciliation-registre-produits-controles-toutes-15min": {
        "task": "infrastructure.taches_celery.reconcilier_registre_produits_controles",
        "schedule": 900.0,
    },
}
