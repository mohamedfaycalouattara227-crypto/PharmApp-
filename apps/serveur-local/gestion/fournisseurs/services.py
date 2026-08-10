"""
gestion/fournisseurs/services.py

Services métier :
  - créer / valider un bon de commande
  - enregistrer une réception (totale ou partielle) qui :
      * crée / complète un Lot dans le catalogue
      * enregistre un MouvementStock (type = RECEPTION) via le service stock
      * publie un événement dans l'outbox (bon_commande.recu)
      * met à jour le statut du BC (PARTIEL / RECU) et son cumul quantite_recue

Toutes les opérations critiques sont exécutées dans une transaction unique
pour garantir l'invariant §3-étape-4 du cahier des charges : « soit toutes
les écritures réussissent, soit aucune ».

Corrections audit v2 :
  - _appliquer_mouvement_stock_reception() : suppression de l'appel à
    ServiceStock.enregistrer_reception() qui n'existe pas. Remplacement par
    une implémentation directe et sûre utilisant select_for_update() sur le
    Lot pour éviter les race conditions sur les réceptions simultanées.
  - _publier_evenement() : correction du nom de classe EvenementOutbox →
    EntreeOutbox (vrai nom dans infrastructure.outbox.modeles), et correction
    des noms de champs : aggregat→modele_source, aggregat_id→id_objet,
    payload→charge_utile.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from gestion.exceptions import PermissionRefusee
from gestion.fournisseurs.models import (
    BonCommande,
    Fournisseur,
    LigneBonCommande,
    LigneReception,
    ReceptionBonCommande,
    StatutBonCommande,
)

logger = logging.getLogger("pharmapp.fournisseurs")


# ─── Erreurs spécifiques ─────────────────────────────────────────────────────


class ErreurFournisseur(Exception):
    """Erreur métier générique du module fournisseurs."""


class BonCommandeNonModifiable(ErreurFournisseur):
    pass


class BonCommandeNonReceptionnable(ErreurFournisseur):
    pass


class QuantiteReceptionInvalide(ErreurFournisseur):
    pass


# ─── DTO d'entrée ─────────────────────────────────────────────────────────────


@dataclass
class LigneBCEntree:
    medicament_id: uuid.UUID
    quantite: int
    prix_unitaire_ht: Decimal
    taux_tva: Decimal = Decimal("0.00")
    notes: str = ""


@dataclass
class LigneReceptionEntree:
    ligne_bc_id: uuid.UUID
    quantite_recue: int
    numero_lot: str
    date_peremption: date
    prix_achat_unitaire: Decimal


# ─── Numérotation ─────────────────────────────────────────────────────────────


def _generer_numero_bon_commande() -> str:
    """
    Génère un numéro BC-YYYY-NNNNN unique et strictement croissant sur l'année.

    FIX RACE CONDITION : utilise CompteurNumerotation avec SELECT FOR UPDATE
    à l'intérieur de la transaction atomique appelante.  L'ancienne implémentation
    (Max() sur la colonne numero) pouvait retourner le même numéro à deux
    transactions concurrentes — la deuxième plantait sur le UNIQUE constraint,
    rejetant un bon de commande valide.

    Doit être appelée à l'intérieur d'un bloc transaction.atomic().
    """
    from gestion.parametrage.models import (
        CompteurNumerotation,
        TypeCompteur,
        appliquer_format_numero,
    )
    now   = timezone.now()
    annee = now.year
    mois  = now.month

    compteur, _ = (
        CompteurNumerotation.objects
        .select_for_update()
        .get_or_create(type=TypeCompteur.BON_COMMANDE, annee=annee)
    )
    compteur.sequence += 1
    compteur.save(update_fields=["sequence"])

    # Format fixe pour les BC (non configurable via l'UI pour l'instant)
    gabarit = "BC-{YYYY}-{NNNNN}"
    return appliquer_format_numero(gabarit, annee, mois, compteur.sequence)


# ─── Service principal ───────────────────────────────────────────────────────


class ServiceFournisseurs:
    """Point d'entrée unique pour la logique métier fournisseurs/achats."""

    # ── Bons de commande ────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def creer_bon_commande(
        *,
        utilisateur,
        fournisseur_id: uuid.UUID,
        lignes: List[LigneBCEntree],
        date_livraison_prevue: Optional[date] = None,
        notes: str = "",
    ) -> BonCommande:
        if not lignes:
            raise ErreurFournisseur("Un bon de commande doit contenir au moins une ligne.")

        fournisseur = Fournisseur.objects.select_for_update().get(pk=fournisseur_id, actif=True)

        bc = BonCommande.objects.create(
            numero=_generer_numero_bon_commande(),
            fournisseur=fournisseur,
            statut=StatutBonCommande.BROUILLON,
            date_livraison_prevue=date_livraison_prevue,
            cree_par=utilisateur,
            notes=notes,
        )
        for ligne in lignes:
            if ligne.quantite <= 0:
                raise ErreurFournisseur("Toute quantité de ligne doit être strictement positive.")
            LigneBonCommande.objects.create(
                bon_commande=bc,
                medicament_id=ligne.medicament_id,
                quantite_commandee=ligne.quantite,
                prix_unitaire_ht=ligne.prix_unitaire_ht,
                taux_tva=ligne.taux_tva,
                notes=ligne.notes,
            )
        bc.recalculer_totaux()
        bc.save(update_fields=["total_ht", "total_tva", "total_ttc"])

        _publier_evenement("bon_commande.cree", bc)
        logger.info("BC %s créé par %s (%d lignes)", bc.numero, utilisateur, len(lignes))
        return bc

    @staticmethod
    @transaction.atomic
    def envoyer_bon_commande(*, utilisateur, bon_commande_id: uuid.UUID) -> BonCommande:
        bc = BonCommande.objects.select_for_update().get(pk=bon_commande_id)
        if bc.statut != StatutBonCommande.BROUILLON:
            raise BonCommandeNonModifiable(
                f"Le BC {bc.numero} est déjà à l'état « {bc.get_statut_display()} »."
            )
        bc.statut = StatutBonCommande.ENVOYE
        bc.envoye_le = timezone.now()
        bc.save(update_fields=["statut", "envoye_le", "modifie_le"])
        _publier_evenement("bon_commande.envoye", bc)
        return bc

    @staticmethod
    @transaction.atomic
    def annuler_bon_commande(
        *, utilisateur, bon_commande_id: uuid.UUID, motif: str
    ) -> BonCommande:
        bc = BonCommande.objects.select_for_update().get(pk=bon_commande_id)
        if bc.statut in (StatutBonCommande.RECU, StatutBonCommande.CLOTURE):
            raise BonCommandeNonModifiable(
                "Un BC déjà entièrement réceptionné ne peut pas être annulé."
            )
        bc.statut = StatutBonCommande.ANNULE
        bc.annule_le = timezone.now()
        bc.motif_annulation = motif
        bc.save(update_fields=["statut", "annule_le", "motif_annulation", "modifie_le"])
        _publier_evenement("bon_commande.annule", bc)
        return bc

    # ── Réception ───────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def receptionner(
        *,
        utilisateur,
        bon_commande_id: uuid.UUID,
        lignes: List[LigneReceptionEntree],
        numero_bordereau: str = "",
        notes: str = "",
    ) -> ReceptionBonCommande:
        """
        Enregistre une réception, crée les lots, alimente le stock,
        met à jour le BC et publie l'événement outbox.
        """
        if not lignes:
            raise ErreurFournisseur("Une réception doit contenir au moins une ligne.")

        bc = BonCommande.objects.select_for_update().get(pk=bon_commande_id)
        if not bc.est_receptionnable():
            raise BonCommandeNonReceptionnable(
                f"Le BC {bc.numero} n'est pas dans un état permettant la réception "
                f"(actuel : {bc.get_statut_display()})."
            )

        reception = ReceptionBonCommande.objects.create(
            bon_commande=bc,
            numero_bordereau=numero_bordereau,
            date_reception=timezone.now(),
            recu_par=utilisateur,
            notes=notes,
        )

        for entree in lignes:
            ligne_bc = LigneBonCommande.objects.select_for_update().get(
                pk=entree.ligne_bc_id, bon_commande=bc
            )
            if entree.quantite_recue <= 0:
                raise QuantiteReceptionInvalide(
                    "La quantité reçue doit être strictement positive."
                )
            if ligne_bc.quantite_recue + entree.quantite_recue > ligne_bc.quantite_commandee:
                raise QuantiteReceptionInvalide(
                    f"Sur-livraison refusée sur « {ligne_bc.medicament.nom} » : "
                    f"restant {ligne_bc.quantite_restante}, reçu {entree.quantite_recue}."
                )

            lot = _obtenir_ou_creer_lot(
                medicament=ligne_bc.medicament,
                numero_lot=entree.numero_lot,
                date_peremption=entree.date_peremption,
                prix_achat=entree.prix_achat_unitaire,
                fournisseur=bc.fournisseur,
            )

            _appliquer_mouvement_stock_reception(
                lot=lot,
                quantite=entree.quantite_recue,
                effectue_par=utilisateur,
                reference=f"BC:{bc.numero} / REC:{reception.id}",
            )

            LigneReception.objects.create(
                reception=reception,
                ligne_bon_commande=ligne_bc,
                lot=lot,
                quantite_recue=entree.quantite_recue,
                numero_lot=entree.numero_lot,
                date_peremption=entree.date_peremption,
                prix_achat_unitaire=entree.prix_achat_unitaire,
            )

            ligne_bc.quantite_recue += entree.quantite_recue
            ligne_bc.save(update_fields=["quantite_recue"])

        # Mise à jour statut BC
        tout_recu = all(l.est_solde for l in bc.lignes.all())
        bc.statut = (
            StatutBonCommande.RECU if tout_recu else StatutBonCommande.PARTIEL
        )
        bc.save(update_fields=["statut", "modifie_le"])

        _publier_evenement(
            "bon_commande.recu" if tout_recu else "bon_commande.recu_partiel",
            bc,
            payload_extra={"reception_id": str(reception.id)},
        )
        logger.info(
            "Réception %s enregistrée pour BC %s (statut=%s)",
            reception.id, bc.numero, bc.statut,
        )
        return reception


# ─── Helpers internes ────────────────────────────────────────────────────────


def _obtenir_ou_creer_lot(*, medicament, numero_lot, date_peremption, prix_achat, fournisseur):
    """
    Cherche un lot existant (même médicament + même numéro_lot + même péremption),
    sinon en crée un nouveau. Le schéma exact de `Lot` est défini dans
    gestion.catalogue.models — on utilise seulement les champs universels.
    """
    from gestion.catalogue.models import Lot

    lot, cree = Lot.objects.get_or_create(
        medicament=medicament,
        numero_lot=numero_lot,
        date_peremption=date_peremption,
        defaults={
            "quantite_initiale": 0,
            "quantite_disponible": 0,
            "prix_achat_unitaire": prix_achat,
        },
    )
    # On aligne le prix d'achat si un champ existe (rétro-compatible)
    if hasattr(lot, "fournisseur_id"):
        lot.fournisseur = fournisseur
        lot.save(update_fields=["fournisseur"])
    if not cree and hasattr(lot, "prix_achat_unitaire") and lot.prix_achat_unitaire != prix_achat:
        # On garde le premier prix historique — jamais d'écrasement silencieux
        logger.debug("Lot %s prix inchangé (historique conservé)", lot.pk)
    return lot


def _appliquer_mouvement_stock_reception(*, lot, quantite, effectue_par, reference: str):
    """
    Applique un mouvement RECEPTION sur un Lot déjà créé/récupéré par
    _obtenir_ou_creer_lot().

    CORRECTION AUDIT v2 :
      - L'appel à ServiceStock.enregistrer_reception() a été supprimé :
        cette méthode n'existe pas (la vraie API est receptionner_livraison()
        avec une signature totalement différente qui crée elle-même les lots).
      - Le fallback existait mais contournait select_for_update(), exposant
        les réceptions simultanées à des race conditions.
      - L'implémentation correcte acquiert un verrou row-level sur le Lot
        (select_for_update) DANS la transaction atomique déjà ouverte par
        l'appelant (ServiceFournisseurs.receptionner) avant toute écriture.

    Invariant : cette fonction est toujours appelée à l'intérieur d'un
    transaction.atomic() — la transaction de receptionner(). Le verrou
    select_for_update est donc effectif et protège contre les réceptions
    concurrentes sur le même lot.
    """
    from gestion.catalogue.models import Lot as LotModel
    from gestion.stocks.models import MouvementStock, TypeMouvement

    # Verrouillage row-level pour cohérence sous charge concurrente
    lot_verrouille = (
        LotModel.objects
        .select_for_update()
        .get(pk=lot.pk)
    )

    quantite_avant = lot_verrouille.quantite_disponible
    quantite_apres = quantite_avant + quantite

    MouvementStock.objects.create(
        lot=lot_verrouille,
        type_mouvement=TypeMouvement.RECEPTION,
        quantite=quantite,
        quantite_avant=quantite_avant,
        quantite_apres=quantite_apres,
        motif="Réception fournisseur",
        reference_document=reference,
        effectue_par=effectue_par,
    )

    lot_verrouille.quantite_disponible = quantite_apres
    lot_verrouille.save(update_fields=["quantite_disponible"])

    # Propager la valeur mise à jour sur l'objet passé en argument
    # pour que l'appelant ait un état cohérent (pas de re-lecture nécessaire).
    lot.quantite_disponible = quantite_apres

    logger.debug(
        "MouvementStock RECEPTION créé : lot=%s %d → %d (ref=%s)",
        lot_verrouille.pk, quantite_avant, quantite_apres, reference,
    )


def _publier_evenement(type_evt: str, bc: BonCommande, payload_extra: Optional[dict] = None):
    """
    Publie un événement dans l'outbox transactionnelle.

    CORRECTION AUDIT v2 :
      - Classe importée corrigée : EvenementOutbox → EntreeOutbox
        (vrai nom dans infrastructure.outbox.modeles).
      - Champs corrigés :
          aggregat      → modele_source
          aggregat_id   → id_objet
          payload       → charge_utile
      - On utilise EntreeOutbox.creer() (méthode de classe dédiée) plutôt que
        .objects.create() directement, pour bénéficier des valeurs par défaut
        et de la logique de validation centralisée.
    """
    try:
        from infrastructure.outbox.modeles import EntreeOutbox
    except Exception:  # pragma: no cover — outbox non migrée en test unitaire isolé
        logger.warning("Outbox indisponible — événement %s non publié pour BC %s", type_evt, bc.numero)
        return

    charge_utile = {
        "bon_commande_id": str(bc.id),
        "numero": bc.numero,
        "fournisseur_id": str(bc.fournisseur_id),
        "statut": bc.statut,
        "total_ttc": str(bc.total_ttc),
    }
    if payload_extra:
        charge_utile.update(payload_extra)

    EntreeOutbox.creer(
        type_evenement=type_evt,
        charge_utile=charge_utile,
        id_objet=bc.id,
        modele_source="fournisseurs.BonCommande",
    )
    logger.debug("Événement outbox publié : %s (BC %s)", type_evt, bc.numero)
