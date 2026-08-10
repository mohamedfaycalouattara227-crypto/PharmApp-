"""
apps/synchronisation/services.py
Services d'ingestion et de traitement des événements de synchronisation.

ServiceIngestion : reçoit un événement depuis un serveur local,
                   vérifie l'idempotence, persiste et route le traitement.

RouteurEvenements : distribue chaque type d'événement vers son handler.
                    Pattern identique à ProcesseurOutbox.ROUTAGE côté local —
                    cohérence architecturale délibérée.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.identite.models import Officine
from apps.synchronisation.models import EvenementSync, StatutTraitement, TypeEvenement

logger = logging.getLogger("pharmapp_cloud.synchronisation")


# ─── DTO entrant ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DonneesEvenement:
    """Données validées d'un événement entrant (post-sérialisation)."""
    uuid: UUID
    type_evenement: str
    version_schema: int
    timestamp_local: datetime
    charge_utile: dict[str, Any]


@dataclass(frozen=True)
class ResultatIngestion:
    uuid: str
    statut: str          # "reçu" | "déjà_connu"
    message: str


# ─── Handlers par type d'événement ────────────────────────────────────────────

class HandlersEvenements:
    """
    Handlers de traitement par type d'événement.
    Chaque handler reçoit l'EvenementSync persisté et l'Officine émettrice.

    Phase 1 : les handlers sont des stubs qui marquent l'événement TRAITE
              et loguent la charge utile. Les agrégations réelles seront
              implémentées en Phase 2.
    """

    @staticmethod
    def _marquer_traite(evenement: EvenementSync) -> None:
        evenement.statut_traitement = StatutTraitement.TRAITE
        evenement.traite_le = timezone.now()
        evenement.save(update_fields=["statut_traitement", "traite_le"])

    @staticmethod
    def _marquer_echec(evenement: EvenementSync, message: str) -> None:
        evenement.statut_traitement = StatutTraitement.ECHEC
        evenement.traite_le = timezone.now()
        evenement.message_erreur = message[:500]
        evenement.save(update_fields=["statut_traitement", "traite_le", "message_erreur"])

    @classmethod
    def traiter_vente(cls, evenement: EvenementSync, officine: Officine) -> None:
        """
        Phase 1 : enregistre la vente agrégée (total, nb lignes).
        Phase 2 : alimentera les statistiques globales et la disponibilité mobile.
        """
        charge = evenement.charge_utile
        logger.info(
            "Vente reçue",
            extra={
                "officine": officine.code,
                "vente_uuid": charge.get("id"),
                "total": charge.get("total"),
                "nb_lignes": len(charge.get("lignes", [])),
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_stock(cls, evenement: EvenementSync, officine: Officine) -> None:
        """
        Phase 1 : log le mouvement de stock.
        Phase 2 : mettra à jour la disponibilité médicament pour l'app mobile.
        """
        charge = evenement.charge_utile
        logger.info(
            "Mouvement stock reçu",
            extra={
                "officine": officine.code,
                "type": evenement.type_evenement,
                "medicament_id": charge.get("medicament_id"),
                "quantite": charge.get("quantite"),
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_catalogue(cls, evenement: EvenementSync, officine: Officine) -> None:
        """
        Phase 1 : log la modification catalogue.
        Phase 2 : agrégation prix de référence pour l'app mobile.
        """
        charge = evenement.charge_utile
        logger.info(
            "Événement catalogue reçu",
            extra={
                "officine": officine.code,
                "type": evenement.type_evenement,
                "medicament_id": charge.get("medicament_id"),
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_client(cls, evenement: EvenementSync, officine: Officine) -> None:
        """
        Phase 1 : log uniquement (données clients sensibles, non agrégées côté cloud).
        """
        logger.info(
            "Événement client reçu (non agrégé)",
            extra={
                "officine": officine.code,
                "type": evenement.type_evenement,
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_assistance(cls, evenement: EvenementSync, officine: Officine) -> None:
        """
        Demande d'assistance — Phase 4 : déclenchera une notification (email/Slack).
        """
        charge = evenement.charge_utile
        logger.warning(
            "DEMANDE D'ASSISTANCE",
            extra={
                "officine": officine.code,
                "officine_id": str(officine.id),
                "probleme": charge.get("probleme", "Non précisé"),
                "contact": charge.get("contact", ""),
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_erreur_critique(cls, evenement: EvenementSync, officine: Officine) -> None:
        """Erreur critique remontée depuis le serveur local."""
        charge = evenement.charge_utile
        logger.error(
            "ERREUR CRITIQUE SERVEUR LOCAL",
            extra={
                "officine": officine.code,
                "module": charge.get("module"),
                "message": charge.get("message"),
                "version": charge.get("version_logiciel"),
            },
        )
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_heartbeat(cls, evenement: EvenementSync, officine: Officine) -> None:
        """Signal de vie — mis à jour via derniere_connexion dans l'auth."""
        cls._marquer_traite(evenement)

    @classmethod
    def traiter_inconnu(cls, evenement: EvenementSync, officine: Officine) -> None:
        """Type d'événement non reconnu — marqué IGNORE, jamais silencieux."""
        logger.warning(
            "Type d'événement inconnu reçu",
            extra={
                "officine": officine.code,
                "type_evenement": evenement.type_evenement,
            },
        )
        evenement.statut_traitement = StatutTraitement.IGNORE
        evenement.traite_le = timezone.now()
        evenement.message_erreur = f"Type non reconnu : {evenement.type_evenement}"
        evenement.save(update_fields=["statut_traitement", "traite_le", "message_erreur"])


# ─── Routeur ──────────────────────────────────────────────────────────────────

class RouteurEvenements:
    """
    Distribue chaque type_evenement vers son handler.
    Un type inconnu → traiter_inconnu (jamais silencieux — règle architecturale).
    """

    ROUTAGE: dict = {
        TypeEvenement.VENTE_CREEE:   HandlersEvenements.traiter_vente,
        TypeEvenement.VENTE_ANNULEE: HandlersEvenements.traiter_vente,
        TypeEvenement.AVOIR_CREE:    HandlersEvenements.traiter_vente,

        TypeEvenement.STOCK_AJUSTE:        HandlersEvenements.traiter_stock,
        TypeEvenement.RECEPTION_LIVRAISON: HandlersEvenements.traiter_stock,
        TypeEvenement.ALERTE_STOCK:        HandlersEvenements.traiter_stock,

        TypeEvenement.MEDICAMENT_CREE:    HandlersEvenements.traiter_catalogue,
        TypeEvenement.MEDICAMENT_MODIFIE: HandlersEvenements.traiter_catalogue,
        TypeEvenement.PRIX_MODIFIE:       HandlersEvenements.traiter_catalogue,

        TypeEvenement.CLIENT_CREE:      HandlersEvenements.traiter_client,
        TypeEvenement.CLIENT_MODIFIE:   HandlersEvenements.traiter_client,
        TypeEvenement.CLIENT_ANONYMISE: HandlersEvenements.traiter_client,

        TypeEvenement.DEMANDE_ASSISTANCE: HandlersEvenements.traiter_assistance,
        TypeEvenement.ERREUR_CRITIQUE:    HandlersEvenements.traiter_erreur_critique,
        TypeEvenement.HEARTBEAT:          HandlersEvenements.traiter_heartbeat,
    }

    @classmethod
    def router(cls, evenement: EvenementSync, officine: Officine) -> None:
        handler = cls.ROUTAGE.get(evenement.type_evenement, HandlersEvenements.traiter_inconnu)
        handler(evenement, officine)


# ─── Service d'ingestion ──────────────────────────────────────────────────────

class ServiceIngestion:
    """
    Point d'entrée unique pour l'ingestion d'un événement de synchronisation.

    Garanties :
    - Idempotence : un UUID déjà connu retourne ResultatIngestion("déjà_connu")
                    sans créer de doublon ni échouer.
    - Atomicité   : l'EvenementSync est persisté avant tout traitement.
    - Isolation   : l'officine est résolue depuis l'objet request.user (déjà authentifié).
    """

    @classmethod
    def ingerer(
        cls,
        officine: Officine,
        donnees: DonneesEvenement,
    ) -> ResultatIngestion:
        """
        Ingère un événement de synchronisation.

        Returns:
            ResultatIngestion avec statut "reçu" ou "déjà_connu".
        """
        # ── Idempotence ───────────────────────────────────────────────────────
        if EvenementSync.objects.filter(uuid=donnees.uuid).exists():
            logger.debug(
                "Événement déjà connu — ignoré (idempotence)",
                extra={"uuid": str(donnees.uuid), "officine": officine.code},
            )
            return ResultatIngestion(
                uuid=str(donnees.uuid),
                statut="déjà_connu",
                message="Événement déjà reçu et traité.",
            )

        # ── Persistance ───────────────────────────────────────────────────────
        with transaction.atomic():
            try:
                evenement = EvenementSync.objects.create(
                    uuid=donnees.uuid,
                    officine=officine,
                    type_evenement=donnees.type_evenement,
                    version_schema=donnees.version_schema,
                    timestamp_local=donnees.timestamp_local,
                    charge_utile=donnees.charge_utile,
                    statut_traitement=StatutTraitement.EN_COURS,
                )
            except IntegrityError:
                # Race condition entre deux requêtes simultanées avec le même UUID
                return ResultatIngestion(
                    uuid=str(donnees.uuid),
                    statut="déjà_connu",
                    message="Événement déjà reçu (race condition résolue).",
                )

        # ── Routage traitement ────────────────────────────────────────────────
        # Le traitement s'effectue hors transaction pour ne pas bloquer l'ingestion.
        try:
            RouteurEvenements.router(evenement, officine)
        except Exception as exc:
            logger.exception(
                "Échec du traitement d'un événement",
                extra={"uuid": str(donnees.uuid), "type": donnees.type_evenement},
            )
            HandlersEvenements._marquer_echec(evenement, str(exc))

        logger.info(
            "Événement ingéré",
            extra={
                "uuid": str(donnees.uuid),
                "officine": officine.code,
                "type": donnees.type_evenement,
            },
        )

        return ResultatIngestion(
            uuid=str(donnees.uuid),
            statut="reçu",
            message="Événement reçu et enregistré.",
        )
