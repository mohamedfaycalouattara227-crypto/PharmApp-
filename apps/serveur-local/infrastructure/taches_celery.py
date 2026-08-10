"""
Module : infrastructure/taches_celery.py
Description : Tâches Celery périodiques pour le traitement de l'Outbox,
              la synchronisation cloud et la sauvegarde locale automatique.

Fréquences recommandées :
    - traiter_outbox_periodique          : toutes les 30 secondes
    - verifier_connexion_cloud           : toutes les 60 secondes
    - nettoyer_outbox_traite             : 1 fois par jour à 2h00
    - sauvegarder_base_donnees_locale    : 1 fois par jour à 2h00 (CDC §4.11)
    - verifier_alertes_stock_periodique  : toutes les 15 minutes
    - rejouer_echecs_automatique         : toutes les heures
    - verifier_integrite_audit           : 1 fois par jour à 3h00

Configuration dans celery.py (beat_schedule) :
    CELERY_BEAT_SCHEDULE = {
        "outbox-toutes-30s": {
            "task": "infrastructure.taches_celery.traiter_outbox_periodique",
            "schedule": 30.0,
        },
        "sauvegarde-quotidienne": {
            "task": "infrastructure.taches_celery.sauvegarder_base_donnees_locale",
            "schedule": crontab(hour=2, minute=0),
        },
        ...
    }
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

# ── Imports module-level (requis pour que patch() fonctionne dans les tests) ──
from gestion.sync.services import ServiceSynchronisation
from gestion.stocks.services import ServiceStock
from gestion.produits_controles.services import ServiceProduitControle
from gestion.audit.services import ServiceAudit
from gestion.audit.models import JournalAudit
from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox

logger = logging.getLogger("pharmapp.celery")


@shared_task(
    name="infrastructure.taches_celery.traiter_outbox_periodique",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=120,
    time_limit=180,
)
def traiter_outbox_periodique(self):
    """
    Traite un lot d'entrées Outbox en attente.
    Appelé toutes les 30 secondes par Celery Beat.
    """
    try:
        resultat = ServiceSynchronisation().traiter_outbox(taille_lot=50)
        logger.info(
            "Outbox : %d événement(s) synchronisé(s), %d échec(s).",
            resultat.evenements_envoyes,
            resultat.evenements_en_echec,
        )
        return {
            "traites": resultat.evenements_envoyes,
            "echecs": resultat.evenements_en_echec,
        }
    except Exception as exc:
        logger.error("Outbox : erreur de traitement : %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name="infrastructure.taches_celery.verifier_connexion_cloud",
    soft_time_limit=15,
    time_limit=30,
)
def verifier_connexion_cloud():
    """
    Vérifie la connexion Internet et met à jour l'état de synchronisation.
    Appelé toutes les 60 secondes par Celery Beat.
    """
    try:
        import urllib.request
        urllib.request.urlopen("https://1.1.1.1", timeout=5)
        est_connecte = True
    except Exception:
        est_connecte = False

    ServiceSynchronisation().mettre_a_jour_statut_connexion(est_connecte)
    logger.info(
        "Sync : vérification connexion cloud — %s",
        "EN LIGNE" if est_connecte else "HORS LIGNE",
    )
    return {"est_connecte": est_connecte}


@shared_task(
    name="infrastructure.taches_celery.nettoyer_outbox_traite",
    soft_time_limit=300,
    time_limit=600,
)
def nettoyer_outbox_traite(jours_retention: int = 30):
    """
    Supprime les entrées Outbox traitées de plus de N jours.
    Appelé 1 fois par jour à 2h00.
    """
    date_limite = timezone.now() - timedelta(days=jours_retention)
    supprimees, _ = EntreeOutbox.objects.filter(
        statut=StatutOutbox.TRAITE,
        traite_le__lt=date_limite,
    ).delete()
    logger.info("Outbox : %d entrée(s) traitée(s) supprimée(s).", supprimees)
    return supprimees


@shared_task(
    name="infrastructure.taches_celery.sauvegarder_base_donnees_locale",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=900,
)
def sauvegarder_base_donnees_locale(self):
    """
    Sauvegarde locale quotidienne de la base de données (CDC §4.11).

    - Utilise pg_dump via subprocess pour un dump complet au format SQL.
    - Compresse avec gzip pour économiser l'espace disque.
    - Stocke dans BACKUP_DIR (défaut /backups/) avec horodatage.
    - Applique une rotation : conserve seulement BACKUP_RETENTION_JOURS fichiers.
    - Enregistre l'action dans le journal d'audit.

    Ce mécanisme est INDÉPENDANT de la synchronisation Supabase :
    même si le cloud est inaccessible, la sauvegarde locale protège.

    Appelé à 2h00 par Celery Beat.
    """
    backup_dir = Path(getattr(settings, "BACKUP_DIR", "/backups"))
    retention = int(getattr(settings, "BACKUP_RETENTION_JOURS", 7))
    today = datetime.now().strftime("%Y-%m-%d")
    nom_fichier = f"pharmapp_{today}.sql.gz"
    chemin_sauvegarde = backup_dir / nom_fichier

    # Créer le répertoire si nécessaire
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        logger.error("Sauvegarde : impossible de créer %s : %s", backup_dir, exc)
        raise self.retry(exc=exc)

    # Extraire les paramètres de connexion depuis DATABASE_URL
    database_url = getattr(settings, "DATABASES", {}).get("default", {})
    db_name = database_url.get("NAME", "pharmapp")
    db_user = database_url.get("USER", "pharmapp")
    db_host = database_url.get("HOST", "localhost")
    db_port = str(database_url.get("PORT", "5432"))
    db_password = database_url.get("PASSWORD", "")

    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password

    # Commande pg_dump + gzip en pipeline
    cmd_pg_dump = [
        "pg_dump",
        "--host", db_host,
        "--port", db_port,
        "--username", db_user,
        "--no-password",
        "--format", "plain",
        "--no-owner",
        "--no-acl",
        db_name,
    ]

    logger.info("Sauvegarde : démarrage → %s", chemin_sauvegarde)

    try:
        with open(chemin_sauvegarde, "wb") as f_out:
            pg_proc = subprocess.Popen(
                cmd_pg_dump,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            gzip_proc = subprocess.Popen(
                ["gzip", "-c"],
                stdin=pg_proc.stdout,
                stdout=f_out,
                stderr=subprocess.PIPE,
            )
            pg_proc.stdout.close()
            gzip_stderr = gzip_proc.communicate()[1]
            pg_proc.wait()

        if pg_proc.returncode != 0:
            pg_stderr = pg_proc.stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"pg_dump a échoué (code={pg_proc.returncode}) : {pg_stderr[:500]}"
            )

        taille_octets = chemin_sauvegarde.stat().st_size
        taille_mo = taille_octets / (1024 * 1024)
        logger.info(
            "Sauvegarde : terminée → %s (%.2f Mo)",
            chemin_sauvegarde, taille_mo,
        )

    except FileNotFoundError:
        logger.error(
            "Sauvegarde : pg_dump introuvable. PostgreSQL est-il installé sur ce serveur ?"
        )
        raise self.retry(exc=RuntimeError("pg_dump introuvable"))
    except Exception as exc:
        # Nettoyage du fichier partiel
        if chemin_sauvegarde.exists():
            chemin_sauvegarde.unlink(missing_ok=True)
        logger.error("Sauvegarde : erreur — %s", exc, exc_info=True)
        raise self.retry(exc=exc)

    # ── Rotation : supprimer les anciennes sauvegardes ────────────────────────
    try:
        sauvegardes = sorted(
            backup_dir.glob("pharmapp_*.sql.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for ancienne in sauvegardes[retention:]:
            ancienne.unlink(missing_ok=True)
            logger.info("Sauvegarde : ancienne supprimée → %s", ancienne.name)
    except Exception as exc:
        logger.warning("Sauvegarde : rotation échouée — %s", exc)

    # ── Audit ──────────────────────────────────────────────────────────────────
    try:
        JournalAudit.objects.journaliser(
            type_action="export_donnees",   # TypeAction le plus proche pour une sauvegarde BD
            description=f"Sauvegarde BD locale : {nom_fichier} ({taille_octets / 1_048_576:.2f} Mo)",
            utilisateur=None,               # tâche système automatique
            severite="info",
            adresse_ip="127.0.0.1",
            id_objet=nom_fichier,
            modele_source="base_de_donnees",
            donnees_supplementaires={
                "fichier": nom_fichier,
                "taille_octets": taille_octets,
                "repertoire": str(backup_dir),
            },
        )
    except Exception as exc:
        logger.warning("Sauvegarde : audit non enregistré — %s", exc)
        # L'audit ne doit pas bloquer ni masquer la sauvegarde

    return {
        "fichier": nom_fichier,
        "taille_octets": taille_octets,
        "sauvegardes_conservees": min(len(sauvegardes), retention),
    }


@shared_task(
    name="infrastructure.taches_celery.verifier_alertes_stock_periodique",
    soft_time_limit=120,
    time_limit=180,
)
def verifier_alertes_stock_periodique():
    """
    Vérifie les niveaux de stock et crée les alertes manquantes.
    Appelé toutes les 15 minutes par Celery Beat.
    """
    try:
        alertes = ServiceStock().verifier_alertes_stock()
        if alertes:
            logger.warning("Stock : %d alerte(s) détectée(s).", len(alertes))
        return {"alertes_gerees": len(alertes)}
    except Exception as exc:
        logger.error("Alertes stock : erreur — %s", exc, exc_info=True)
        return {"erreur": str(exc)}


@shared_task(
    name="infrastructure.taches_celery.rejouer_echecs_automatique",
    soft_time_limit=300,
    time_limit=600,
)
def rejouer_echecs_automatique():
    """
    Remet en file les événements Outbox en échec (backoff épuisé).
    Appelé toutes les heures par Celery Beat.
    """
    try:
        rejoues = ServiceSynchronisation().rejouer_echecs(limit=20)
        logger.info("Outbox : %d événement(s) en échec remis en file.", rejoues)
        return {"rejoues": rejoues}
    except Exception as exc:
        logger.error("Rejouer échecs : erreur — %s", exc, exc_info=True)
        return {"erreur": str(exc)}


@shared_task(
    name="infrastructure.taches_celery.verifier_integrite_audit",
    soft_time_limit=300,
    time_limit=600,
)
def verifier_integrite_audit():
    """
    Vérifie l'intégrité SHA-256 du journal d'audit.
    Appelé 1 fois par jour à 3h00 par Celery Beat.
    """
    try:
        resultat = ServiceAudit().verifier_integrite_journal()
        if not resultat.get("integrite_ok", True):
            logger.critical(
                "ALERTE SÉCURITÉ : intégrité du journal d'audit compromise ! "
                "Entrées corrompues : %s",
                resultat.get("corrompues", []),
            )
        else:
            logger.info("Audit : intégrité du journal vérifiée (%d entrées).", resultat.get("total", 0))
        return resultat
    except Exception as exc:
        logger.error("Intégrité audit : erreur — %s", exc, exc_info=True)
        return {"erreur": str(exc)}


@shared_task(
    name="infrastructure.taches_celery.reconcilier_registre_produits_controles",
    bind=True,
    max_retries=3,
    soft_time_limit=300,
    time_limit=600,
)
def reconcilier_registre_produits_controles(self, fenetre_heures: int = 48):
    """
    Détecte les LigneVente de produits contrôlés dépourvues d'entrée
    SORTIE_VENTE dans le registre réglementaire et les crée à posteriori.

    Filet de sécurité pour le comportement "fail-open" volontaire de
    ServiceProduitControle.enregistrer_sortie_vente() lors d'une vente
    (gestion.ventes.services.ServiceVente.traiter_vente) : cet appel ne
    doit jamais bloquer une vente, mais toute entrée manquée doit être
    rattrapée ici, sans quoi le registre reste silencieusement incomplet
    — inacceptable pour un document soumis aux inspections DGPML.

    Fréquence : toutes les 15 minutes (voir pharmapp/celery.py).

    Args:
        fenetre_heures: profondeur de scan. Défaut 48h — largement au-delà
            du délai typique entre une vente et l'exécution du job (15 min),
            mais suffisamment court pour rester performant. Peut être
            augmenté ponctuellement après un incident majeur.

    Returns:
        dict avec scannees, rattrapees, echecs.
    """
    from django.db import transaction as _tx
    from gestion.ventes.models import LigneVente, StatutVente

    date_limite = timezone.now() - timedelta(hours=fenetre_heures)

    # LigneVente candidates : produit contrôlé, vente validée, sans entrée
    # registre liée (via le OneToOneField ajouté en migration 0002), dans
    # la fenêtre de scan.
    candidates_qs = (
        LigneVente.objects
        .select_related("medicament", "lot", "vente", "vente__vendeur", "vente__ordonnance")
        .filter(
            medicament__est_produit_controle=True,
            vente__statut=StatutVente.VALIDEE,
            vente__cree_le__gte=date_limite,
            entree_registre_controle__isnull=True,
        )
        .order_by("vente__cree_le")
    )

    scannees = candidates_qs.count()
    if scannees == 0:
        logger.info("Réconciliation registre : aucune ligne à rattraper.")
        return {"scannees": 0, "rattrapees": 0, "echecs": 0}

    logger.critical(
        "Réconciliation registre : %d ligne(s) de produits contrôlés "
        "sans entrée SORTIE_VENTE détectée(s) sur les %d dernière(s) heure(s).",
        scannees, fenetre_heures,
    )

    service = ServiceProduitControle()
    rattrapees = 0
    echecs = 0

    # Boucle une ligne à la fois avec sa propre transaction : un échec sur
    # une ligne ne doit pas empêcher les autres d'être rattrapées.
    for ligne in candidates_qs.iterator(chunk_size=100):
        try:
            with _tx.atomic():
                service.enregistrer_sortie_vente(
                    medicament=ligne.medicament,
                    lot=ligne.lot,
                    quantite=ligne.quantite,
                    vendeur=ligne.vente.vendeur,
                    ordonnance=ligne.vente.ordonnance,
                    ligne_vente=ligne,
                    cree_par_reconciliation=True,
                    # Rattrapage a posteriori : le lot a déjà été décrémenté
                    # lors de la vente d'origine.
                    stock_avant=ligne.lot.quantite_disponible + ligne.quantite,
                    motif="Délivrance sur ordonnance (rattrapée)",
                    notes_reglementaires=(
                        f"Entrée créée à posteriori par le job de "
                        f"réconciliation le {timezone.now().isoformat()} — "
                        f"l'écriture initiale au moment de la vente "
                        f"'{ligne.vente.numero}' avait échoué. "
                        f"À auditer manuellement."
                    ),
                )
            rattrapees += 1
            logger.warning(
                "Réconciliation registre : ligne_vente=%s rattrapée "
                "(vente=%s, medicament_id=%s, quantite=%d).",
                ligne.id, ligne.vente.numero,
                str(ligne.medicament_id), ligne.quantite,
            )
        except Exception as exc:
            echecs += 1
            logger.critical(
                "Réconciliation registre : ÉCHEC sur ligne_vente=%s "
                "(vente=%s) — sera retenté au prochain cycle. Erreur : %s",
                ligne.id, ligne.vente.numero, exc,
                exc_info=True,
            )

    # Trace d'audit : le titulaire doit pouvoir constater qu'un rattrapage
    # a eu lieu (obligation de traçabilité DGPML). JournalAudit.objects.journaliser
    # est utilisé directement (plutôt qu'une méthode dédiée de ServiceAudit,
    # qui n'en a pas pour un événement système sans registre unique associé).
    if rattrapees > 0 or echecs > 0:
        try:
            from gestion.audit.models import JournalAudit
            JournalAudit.objects.journaliser(
                type_action="registre_produits_controles_reconcilie",
                description=(
                    f"Réconciliation registre produits contrôlés : "
                    f"{scannees} ligne(s) scannée(s), {rattrapees} rattrapée(s), "
                    f"{echecs} échec(s) sur les {fenetre_heures}h précédentes."
                ),
                severite="critique",
                donnees_supplementaires={
                    "scannees": scannees,
                    "rattrapees": rattrapees,
                    "echecs": echecs,
                    "fenetre_heures": fenetre_heures,
                },
            )
        except Exception as exc:
            logger.error(
                "Réconciliation registre : échec de l'écriture d'audit "
                "(le rattrapage lui-même a réussi) : %s", exc, exc_info=True,
            )

    return {"scannees": scannees, "rattrapees": rattrapees, "echecs": echecs}
