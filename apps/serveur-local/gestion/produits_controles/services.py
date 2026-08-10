"""
gestion/produits_controles/services.py — Étape 13

ServiceProduitControle : Gestion des entrées du registre réglementaire.
Appelé depuis services.py de ventes lors d'une transaction impliquant
un produit contrôlé (stupéfiant / psychotrope).

Règles ANRP (Burkina Faso) :
  - Toute délivrance de produit contrôlé doit figurer dans le registre.
  - Une ordonnance sécurisée est OBLIGATOIRE (vérifiée dans services.py ventes).
  - Le nom du patient est chiffré AES-256-GCM en base.
  - Le registre est IMMUABLE (pas de DELETE ni UPDATE depuis l'UI).
"""

import logging
from typing import Optional

from django.db import transaction
from django.conf import settings

logger = logging.getLogger("pharmapp.produits_controles")


class ServiceProduitControle:
    """Service métier pour le registre des produits contrôlés."""

    def enregistrer_sortie_vente(
        self,
        *,
        medicament,
        lot,
        ordonnance,
        quantite: int,
        vendeur,
        superviseur=None,
        patient_nom: str = "",
        prescripteur_nom: str = "",
        prescripteur_num_ordre: str = "",
        motif: str = "Délivrance sur ordonnance",
        ligne_vente=None,
        cree_par_reconciliation: bool = False,
        notes_reglementaires: str = "",
        stock_avant: int | None = None,
    ):
        """
        Crée une entrée SORTIE_VENTE dans le registre.

        Doit être appelé dans la même transaction atomique que la vente.
        """
        from gestion.produits_controles.models import (
            RegistreProduitControle,
            TypeMouvementControle,
        )
        from gestion.catalogue.models import Lot

        # Stock avant/après consignés au registre.
        # CONTRAT EXPLICITE : `stock_avant` doit être fourni par l'appelant qui
        # a déjà décrémenté le lot (vente, réconciliation) — il connaît seul la
        # valeur d'origine. Sans lui, on considère que le lot n'a pas encore été
        # décrémenté et l'on part de sa quantité courante.
        # (Auparavant on déduisait `lot.quantite_disponible + quantite`, ce qui
        # falsifiait le registre dès que l'appelant n'avait pas décrémenté.)
        if stock_avant is None:
            stock_avant = lot.quantite_disponible
        stock_apres = stock_avant - quantite

        entree = RegistreProduitControle(
            medicament=medicament,
            lot=lot,
            numero_lot_fabricant=lot.numero_lot or "",
            type_mouvement=TypeMouvementControle.SORTIE_VENTE,
            quantite_mouvement=quantite,
            unite=getattr(medicament, "forme_pharmaceutique", "") or "unité",
            stock_avant=max(0, stock_avant),
            stock_apres=max(0, stock_apres),
            ordonnance=ordonnance,
            prescripteur_nom=prescripteur_nom or (
                ordonnance.prescripteur_nom if ordonnance else ""
            ),
            prescripteur_num_ordre=prescripteur_num_ordre,
            effectue_par=vendeur,
            supervise_par=superviseur,
            motif=motif,
            ligne_vente=ligne_vente,
            cree_par_reconciliation=cree_par_reconciliation,
            notes_reglementaires=notes_reglementaires,
        )
        # Chiffrement du nom patient via la propriété du modèle
        if patient_nom:
            entree.patient_nom = patient_nom
        elif ordonnance and hasattr(ordonnance, "patient_nom"):
            entree.patient_nom = ordonnance.patient_nom or ""

        entree.save()

        # Audit CRITIQUE (traçabilité réglementaire)
        # CORRECTIF : ServiceAudit n'a jamais eu de méthode générique
        # `enregistrer()` — cet appel levait systématiquement un
        # AttributeError, silencieusement avalé par le except ci-dessous,
        # si bien qu'aucune entrée d'audit n'a jamais été écrite pour une
        # dispensation de produit contrôlé. La méthode réelle est
        # `journaliser_produit_controle`, déjà prévue à cet effet.
        try:
            from gestion.audit.services import ServiceAudit
            ServiceAudit().journaliser_produit_controle(
                registre=entree,
                type_mouvement=entree.type_mouvement,
                utilisateur=vendeur,
            )
        except Exception as exc:
            # Audit non bloquant mais loggué — la traçabilité réglementaire
            # sera assurée par le registre lui-même.
            logger.warning(
                "Audit CRITIQUE non enregistré pour produit contrôlé id=%s : %s",
                str(medicament.id),  # ID uniquement, jamais le nom en clair dans les logs
                type(exc).__name__,
            )

        # Outbox cloud
        try:
            from infrastructure.outbox.modeles import EntreeOutbox
            EntreeOutbox.objects.create(
                type_evenement="EvenementProduitsControlesDelivre",
                id_objet=entree.id,
                charge_utile={
                    "registre_id": str(entree.id),
                    "medicament_id": str(medicament.id),
                    # medicament.nom omis intentionnellement : données médicales
                    # non transmises en clair dans l'outbox (conformité RGPD/santé).
                    "quantite": quantite,
                    "lot_numero": lot.numero_lot,
                    "ordonnance_id": str(ordonnance.id) if ordonnance else None,
                },
            )
        except Exception as exc:
            logger.warning("Outbox produit contrôlé non inscrite : %s", type(exc).__name__)

        logger.info(
            "produit_controle_delivre: medicament_id=%s × %d (lot=%s, ordonnance_id=%s)",
            str(medicament.id),      # ID, jamais le nom en clair
            quantite,
            lot.numero_lot,
            str(ordonnance.id) if ordonnance else "—",  # ID UUID, pas de PII patient
        )
        return entree
