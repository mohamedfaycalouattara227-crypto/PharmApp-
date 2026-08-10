"""
Module : gestion/sync/services.py
Description : Service de synchronisation locale ↔ cloud pour PharmApp.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

# Imports module-level pour que patch() fonctionne dans les tests
from infrastructure.outbox.modeles import EntreeOutbox, StatutOutbox
from gestion.synchronisation.modeles import EtatSynchronisation, ConflitSynchronisation, StatutConnexion, StatutConflit
from infrastructure.outbox.processeur import ProcesseurOutbox

logger = logging.getLogger("pharmapp.sync")


# ─── Types de données ─────────────────────────────────────────────────────────

@dataclass
class ResultatSynchronisation:
    """Résultat d'une opération de synchronisation."""
    succes: bool
    evenements_envoyes: int = 0
    evenements_en_echec: int = 0
    conflits_detectes: int = 0
    message: str = ""
    erreur: str = ""


@dataclass
class StatutSync:
    """État courant de la synchronisation de l'officine."""
    est_connecte: bool = False
    derniere_sync_reussie: Optional[datetime] = None
    evenements_en_attente: int = 0
    evenements_en_echec: int = 0
    conflits_non_resolus: int = 0
    version_schema_locale: str = ""
    version_schema_cloud: str = ""


# ─── Service principal ────────────────────────────────────────────────────────

class ServiceSynchronisation:
    """Service de synchronisation locale ↔ cloud de PharmApp."""

    # Types d'événements qui ne sont jamais synchronisés vers le cloud
    TYPES_EXCLUS_CLOUD = frozenset({
        "acces_sensible",
        "image_ordonnance",
        "connexion_echouee",
    })

    def obtenir_statut(self, officine_id: Optional[uuid.UUID] = None) -> StatutSync:
        """Retourne l'état courant de la synchronisation."""
        try:
            entrees_en_attente = EntreeOutbox.objects.filter(
                statut__in=[StatutOutbox.EN_ATTENTE, StatutOutbox.EN_COURS]
            ).count()
            entrees_en_echec = EntreeOutbox.objects.filter(
                statut=StatutOutbox.ECHEC
            ).count()
            conflits = ConflitSynchronisation.objects.filter(
                statut=StatutConflit.NON_RESOLU
            ).count()

            etat = EtatSynchronisation.objects.order_by("-modifie_le").first()

            return StatutSync(
                est_connecte=etat.statut_connexion == StatutConnexion.EN_LIGNE if etat else False,
                derniere_sync_reussie=etat.derniere_sync_reussie if etat else None,
                evenements_en_attente=entrees_en_attente,
                evenements_en_echec=entrees_en_echec,
                conflits_non_resolus=conflits,
            )
        except Exception as exc:
            logger.error("Sync : erreur lors du calcul du statut : %s", exc)
            return StatutSync()

    def inscrire_dans_outbox(
        self,
        type_evenement: str,
        charge_utile: dict,
        id_objet: Optional[uuid.UUID] = None,
        modele_source: str = "",
        id_utilisateur: Optional[uuid.UUID] = None,
    ) -> Optional[object]:
        """
        Inscrit un événement dans l'Outbox transactionnelle.

        Les événements dans TYPES_EXCLUS_CLOUD sont ignorés.
        """
        if type_evenement in self.TYPES_EXCLUS_CLOUD:
            logger.debug(
                "Sync : événement '%s' exclu du cloud — non inscrit.",
                type_evenement,
            )
            return None

        charge_nettoyee = self._nettoyer_charge(charge_utile)
        entree = EntreeOutbox.creer(
            type_evenement=type_evenement,
            charge_utile=charge_nettoyee,
            id_objet=id_objet,
            modele_source=modele_source,
            id_utilisateur=id_utilisateur,
        )
        return entree

    def detecter_conflits(
        self,
        modele: str,
        id_objet: uuid.UUID,
        donnees_locales: dict,
        donnees_cloud: dict,
    ) -> Optional[object]:
        """
        Détecte et enregistre un conflit entre données locales et cloud.

        Returns:
            ConflitSynchronisation si un conflit est détecté, None sinon.
        """
        if donnees_locales == donnees_cloud:
            return None

        conflit, _ = ConflitSynchronisation.objects.get_or_create(
            modele=modele,
            id_objet=id_objet,
            statut=StatutConflit.NON_RESOLU,
            defaults={
                "donnees_locales": donnees_locales,
                "donnees_cloud": donnees_cloud,
            },
        )
        logger.warning(
            "Sync : conflit détecté — modèle=%s id=%s",
            modele, id_objet,
        )
        return conflit

    def rejouer_echecs(self, limit: int = 20) -> int:
        """
        Remet en file d'attente les entrées Outbox en échec définitif.

        Returns:
            Nombre d'entrées remises en file.
        """
        entrees = list(
            EntreeOutbox.objects.filter(statut=StatutOutbox.ECHEC)[:limit]
        )
        count = 0
        for entree in entrees:
            try:
                entree.rejouer()
                count += 1
            except Exception as exc:
                logger.warning("Sync : impossible de rejouer %s : %s", entree.id, exc)

        if count:
            logger.info("Sync : %d entrée(s) en échec remise(s) en file.", count)
        return count

    def traiter_outbox(self, taille_lot: int = 50) -> ResultatSynchronisation:
        """
        Traite un lot d'entrées Outbox en attente.

        Returns:
            ResultatSynchronisation avec les métriques.
        """
        try:
            processeur = ProcesseurOutbox()
            # Le service est le point d'entrée métier de la synchronisation :
            # l'envoi réseau reste une couture explicite portée par le service
            # (supervision, tests, futurs transports alternatifs), le
            # processeur n'en étant que l'implémentation par défaut.
            processeur._envoyer_vers_cloud = self._envoyer_vers_cloud
            rapport = processeur.traiter_lot(taille=taille_lot)
            return ResultatSynchronisation(
                succes=True,
                evenements_envoyes=rapport.get("traites", 0),
                evenements_en_echec=rapport.get("echecs", 0),
            )
        except Exception as exc:
            logger.error("Sync : erreur traitement Outbox : %s", exc, exc_info=True)
            return ResultatSynchronisation(
                succes=False,
                erreur=str(exc),
            )

    def mettre_a_jour_statut_connexion(
        self,
        est_connecte: bool,
        officine_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Met à jour l'état de connexion de l'officine."""
        etat = EtatSynchronisation.objects.order_by("-modifie_le").first()
        if not etat:
            etat = EtatSynchronisation.objects.create()

        etat.statut_connexion = (
            StatutConnexion.EN_LIGNE if est_connecte else StatutConnexion.HORS_LIGNE
        )
        if est_connecte:
            etat.derniere_sync_reussie = timezone.now()

        etat.save(update_fields=["statut_connexion", "derniere_sync_reussie", "modifie_le"])

        logger.info(
            "Sync : connexion — %s",
            "EN LIGNE" if est_connecte else "HORS LIGNE",
        )

    # ─── Méthodes privées ─────────────────────────────────────────────────────

    def _envoyer_vers_cloud(self, entree) -> None:
        """Envoie une entrée Outbox vers le cloud (délégué au ProcesseurOutbox)."""
        ProcesseurOutbox()._envoyer_vers_cloud(entree)

    def _nettoyer_charge(self, charge: dict) -> dict:
        """Supprime les données sensibles de la charge utile avant synchronisation."""
        CHAMPS_EXCLUS = frozenset({
            "image_chiffree",
            "vecteur_initialisation",
            "mot_de_passe",
            "password",
            "token",
            "secret",
            "empreinte_sha256",
            "cle_chiffrement",
        })
        return {k: v for k, v in charge.items() if k not in CHAMPS_EXCLUS}
