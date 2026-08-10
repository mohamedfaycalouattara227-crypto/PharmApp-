"""
pharmapp/sentry_config.py
Configuration Sentry centralisée (DT-018)

Ce module est importé dans settings.py via :
    from pharmapp.sentry_config import init_sentry
    init_sentry()

Variables d'environnement requises :
  SENTRY_DSN           — DSN fourni par Sentry (obligatoire pour activer)
  SENTRY_ENV           — "production" | "staging" | "development" (défaut: "development")
  SENTRY_RELEASE       — ex. "pharmapp@1.0.2" (optionnel, injecté par CI)
  SENTRY_TRACES_RATE   — taux d'échantillonnage des traces (0.0–1.0, défaut: 0.1)
  SENTRY_PROFILES_RATE — taux profilage performance (0.0–1.0, défaut: 0.05)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("pharmapp.sentry")


def init_sentry() -> None:
    """Initialise le SDK Sentry. No-op si SENTRY_DSN est absent."""
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        logger.info("Sentry désactivé (SENTRY_DSN non défini).")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as exc:
        logger.warning("sentry-sdk non installé — supervision désactivée. (%s)", exc)
        return

    env = os.environ.get("SENTRY_ENV", "development")
    release = os.environ.get("SENTRY_RELEASE", "pharmapp@dev")
    traces_rate = float(os.environ.get("SENTRY_TRACES_RATE", "0.1"))
    profiles_rate = float(os.environ.get("SENTRY_PROFILES_RATE", "0.05"))

    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # INFO et supérieur → breadcrumb
        event_level=logging.ERROR, # ERROR et supérieur → événement Sentry
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
                signals_spans=False,
                cache_spans=True,
            ),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
            sentry_logging,
        ],
        environment=env,
        release=release,
        traces_sample_rate=traces_rate,
        profiles_sample_rate=profiles_rate,
        # Ne jamais envoyer les données patients dans Sentry
        send_default_pii=False,
        # Filtrer les champs sensibles
        before_send=_filtrer_donnees_sensibles,
        before_send_transaction=_filtrer_transaction_sensible,
        # Ignorer les erreurs non actionnables
        ignore_errors=[
            "DisconnectedError",
            "BrokenPipeError",
            "ConnectionResetError",
        ],
    )
    logger.info(
        "Sentry initialisé — env=%s release=%s traces=%.2f",
        env, release, traces_rate,
    )


# ─── Filtres RGPD / confidentialité ─────────────────────────────────────────

_CHAMPS_SENSIBLES = {
    "password", "mot_de_passe", "token", "access", "refresh",
    "ordonnance_key", "encryption_key", "nom_patient_chiffre",
    "pharmapp_csrf", "pharmapp_access", "pharmapp_refresh",
    "authorization", "cookie", "csrftoken",
}


def _filtrer_donnees_sensibles(event: dict, hint: dict) -> dict | None:  # type: ignore[type-arg]
    """Supprime les champs sensibles des événements Sentry avant envoi."""
    _purger_dict_recursif(event.get("request", {}).get("data", {}))
    _purger_dict_recursif(event.get("request", {}).get("cookies", {}))
    _purger_dict_recursif(event.get("request", {}).get("headers", {}))
    return event


def _filtrer_transaction_sensible(event: dict, hint: dict) -> dict | None:  # type: ignore[type-arg]
    return event


def _purger_dict_recursif(obj: object) -> None:
    if not isinstance(obj, dict):
        return
    for cle in list(obj.keys()):
        if cle.lower() in _CHAMPS_SENSIBLES:
            obj[cle] = "[Filtré]"
        else:
            _purger_dict_recursif(obj[cle])
