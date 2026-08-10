"""
gestion/supervision/taches.py
Tâches Celery d'alerting et de supervision (DT-018)

Tâches planifiées (django-celery-beat) :
  - verifier_seuils_stock     : toutes les 30 min
  - verifier_lots_perimees    : toutes les heures
  - verifier_sante_systeme    : toutes les 5 min
  - envoyer_webhook_alerte    : déclenchée à la demande (alerte critique)

Variables d'environnement :
  WEBHOOK_ALERTE_URL   — URL du webhook (Slack, Teams, ntfy…)
  WEBHOOK_SECRET_TOKEN — Jeton Bearer optionnel
  ALERTE_SEUIL_STOCK   — Seuil de stock bas (défaut: 5)
  ALERTE_JOURS_PEREMPTION — Jours avant péremption (défaut: 30)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import requests
from celery import shared_task
from django.db import connection
from django.utils import timezone

logger = logging.getLogger("pharmapp.supervision")

WEBHOOK_URL    = os.environ.get("WEBHOOK_ALERTE_URL", "")
WEBHOOK_TOKEN  = os.environ.get("WEBHOOK_SECRET_TOKEN", "")
SEUIL_STOCK    = int(os.environ.get("ALERTE_SEUIL_STOCK", "5"))
JOURS_PEREMPTION = int(os.environ.get("ALERTE_JOURS_PEREMPTION", "30"))


# ─── Envoi webhook ────────────────────────────────────────────────────────────

def _envoyer_webhook(payload: Dict[str, Any]) -> bool:
    """Envoie un payload JSON vers le webhook configuré. Retourne True si succès."""
    if not WEBHOOK_URL:
        logger.debug("Webhook non configuré (WEBHOOK_ALERTE_URL absent).")
        return False
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"
    try:
        resp = requests.post(
            WEBHOOK_URL, json=payload, headers=headers, timeout=10
        )
        resp.raise_for_status()
        logger.info("Webhook alerte envoyé — statut %d", resp.status_code)
        return True
    except requests.RequestException as exc:
        logger.error("Échec webhook alerte — %s", exc)
        return False


def _format_slack(titre: str, message: str, niveau: str = "warning") -> Dict[str, Any]:
    """Formate un payload compatible Slack Incoming Webhooks."""
    couleur = {"critical": "#FF0000", "warning": "#FFA500", "info": "#36A64F"}.get(
        niveau, "#808080"
    )
    return {
        "attachments": [
            {
                "color": couleur,
                "title": f"[PharmApp] {titre}",
                "text": message,
                "footer": "PharmApp Supervision",
                "ts": int(timezone.now().timestamp()),
            }
        ]
    }


# ─── Tâche : vérifier seuils stock ───────────────────────────────────────────

@shared_task(name="supervision.verifier_seuils_stock", bind=True, max_retries=3)
def verifier_seuils_stock(self) -> Dict[str, Any]:  # type: ignore[type-arg]
    """
    Vérifie les médicaments dont le stock total disponible est ≤ SEUIL_STOCK.
    Envoie une alerte webhook si des médicaments sont en rupture imminente.
    """
    try:
        from gestion.stocks.models import MouvementStock
        from gestion.catalogue.models import Medicament

        medicaments_critiques: List[Dict[str, Any]] = []

        for med in Medicament.objects.filter(est_actif=True).only(
            "id", "nom", "code_barre", "seuil_alerte"
        ):
            seuil = med.seuil_alerte if med.seuil_alerte is not None else SEUIL_STOCK
            stock = getattr(med, "stock_total_disponible", 0) or 0
            if stock <= seuil:
                medicaments_critiques.append({
                    "nom": med.nom,
                    "code_barre": med.code_barre or "N/A",
                    "stock": stock,
                    "seuil": seuil,
                })

        if medicaments_critiques:
            nb = len(medicaments_critiques)
            lignes = "\n".join(
                f"• {m['nom']} : {m['stock']} unités (seuil {m['seuil']})"
                for m in medicaments_critiques[:10]
            )
            if nb > 10:
                lignes += f"\n… et {nb - 10} autres."

            niveau = "critical" if any(m["stock"] == 0 for m in medicaments_critiques) else "warning"
            _envoyer_webhook(
                _format_slack(
                    f"{nb} médicament(s) en stock critique",
                    lignes,
                    niveau=niveau,
                )
            )
            logger.warning("Stock critique : %d médicaments sous seuil.", nb)

        return {"medicaments_critiques": len(medicaments_critiques)}

    except Exception as exc:
        logger.error("verifier_seuils_stock échoué : %s", exc)
        raise self.retry(exc=exc, countdown=60)


# ─── Tâche : vérifier lots périmés ───────────────────────────────────────────

@shared_task(name="supervision.verifier_lots_perimees", bind=True, max_retries=3)
def verifier_lots_perimees(self) -> Dict[str, Any]:  # type: ignore[type-arg]
    """
    Détecte les lots dont la date de péremption est dans moins de JOURS_PEREMPTION jours.
    """
    try:
        from gestion.stocks.models import Lot

        limite = date.today() + timedelta(days=JOURS_PEREMPTION)
        lots = (
            Lot.objects.filter(
                date_expiration__lte=limite,
                date_expiration__gte=date.today(),
                quantite_disponible__gt=0,
            )
            .select_related("medicament")
            .order_by("date_expiration")[:20]
        )

        if lots:
            lignes = "\n".join(
                f"• {lot.medicament.nom} — lot {lot.numero_lot} : périme le {lot.date_expiration} "
                f"({lot.quantite_disponible} unités)"
                for lot in lots
            )
            _envoyer_webhook(
                _format_slack(
                    f"{len(lots)} lot(s) expirant dans {JOURS_PEREMPTION} jours",
                    lignes,
                    niveau="warning",
                )
            )
            logger.warning("Lots périmés imminents : %d lots.", len(lots))

        # Détecter les lots déjà périmés avec stock > 0
        lots_expires = Lot.objects.filter(
            date_expiration__lt=date.today(),
            quantite_disponible__gt=0,
        ).count()
        if lots_expires:
            _envoyer_webhook(
                _format_slack(
                    f"ALERTE : {lots_expires} lot(s) PÉRIMÉ(s) en stock",
                    f"{lots_expires} lot(s) ont dépassé leur date de péremption "
                    "mais présentent encore du stock disponible. Action requise.",
                    niveau="critical",
                )
            )
            logger.error("Lots périmés avec stock non zéro : %d", lots_expires)

        return {"lots_proches": len(lots), "lots_expires": lots_expires}

    except Exception as exc:
        logger.error("verifier_lots_perimees échoué : %s", exc)
        raise self.retry(exc=exc, countdown=120)


# ─── Tâche : santé système ────────────────────────────────────────────────────

@shared_task(name="supervision.verifier_sante_systeme", bind=True, max_retries=1)
def verifier_sante_systeme(self) -> Dict[str, Any]:  # type: ignore[type-arg]
    """
    Vérifie la connectivité DB et Redis.
    Envoie une alerte critique si une dépendance est indisponible.
    """
    problemes: List[str] = []

    # Test DB
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:
        problemes.append(f"Base de données inaccessible : {exc}")
        logger.critical("DB indisponible : %s", exc)

    # Test Redis
    try:
        from django.core.cache import cache
        cache.set("sante_check", "ok", 5)
        val = cache.get("sante_check")
        if val != "ok":
            problemes.append("Redis : set/get incohérent")
    except Exception as exc:
        problemes.append(f"Redis inaccessible : {exc}")
        logger.critical("Redis indisponible : %s", exc)

    # Test file Celery
    try:
        from celery import current_app
        i = current_app.control.inspect(timeout=2.0)
        actifs = i.active()
        if actifs is None:
            problemes.append("Celery worker : aucune réponse (timeout 2s)")
    except Exception as exc:
        problemes.append(f"Celery inspect : {exc}")

    if problemes:
        texte = "\n".join(f"• {p}" for p in problemes)
        _envoyer_webhook(
            _format_slack(
                "CRITIQUE : Défaillance infrastructure",
                texte,
                niveau="critical",
            )
        )

    return {"problemes": len(problemes), "details": problemes}


# ─── Tâche manuelle : alerte arbitraire ──────────────────────────────────────

@shared_task(name="supervision.envoyer_alerte_manuelle")
def envoyer_alerte_manuelle(titre: str, message: str, niveau: str = "warning") -> bool:
    """Déclenche une alerte manuelle (appelée depuis le code métier)."""
    return _envoyer_webhook(_format_slack(titre, message, niveau=niveau))
