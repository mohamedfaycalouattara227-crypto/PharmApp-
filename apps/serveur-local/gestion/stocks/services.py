"""
Module : gestion/stocks/services.py
Description : Service métier pour la gestion des stocks de PharmApp.
"""

import logging
import uuid
from decimal import Decimal
from typing import List, Optional

from django.db import transaction

from gestion.exceptions import (
    PermissionRefusee,
    LotInactif,
    EcartInventaireSignificatif,
)

# Imports module-level pour que patch() fonctionne dans les tests
from gestion.catalogue.models import Lot, Medicament
from gestion.stocks.models import (
    MouvementStock, AlerteStock, NiveauAlerte,
    Inventaire, LigneInventaire,
)

logger = logging.getLogger("pharmapp.stocks")


class ServiceStock:
    """Service métier pour la gestion des stocks."""

    # Seuil d'écart (en %) au-delà duquel une approbation pharmacien adjoint est requise
    SEUIL_ECART_APPROBATION = Decimal("5.00")

    # ─── Ajustement manuel ────────────────────────────────────────────────────

    def ajuster_stock_manuel(
        self,
        lot_id: uuid.UUID,
        nouvelle_quantite: int,
        motif: str,
        utilisateur,
        adresse_ip: str = "",
    ):
        """
        Ajuste manuellement la quantité d'un lot.

        Raises:
            PermissionRefusee: Si l'utilisateur n'est pas gestionnaire_stock+.
            ValueError: Si le lot est introuvable.
            LotInactif: Si le lot est désactivé.
            EcartInventaireSignificatif: Si l'écart dépasse le seuil sans approbation adjoint+.
        """
        # ── 1. Permission (sans DB) ───────────────────────────────────────────
        if not utilisateur.a_permission_role("gestionnaire_stock"):
            raise PermissionRefusee(
                "L'ajustement de stock requiert au moins le rôle gestionnaire_stock."
            )

        # ── 2. Pré-lecture et validation (Lot est mocké dans les tests unitaires) ─
        lot = (
            Lot.objects
            .select_for_update()
            .filter(id=lot_id)
            .first()
        )
        if lot is None:
            raise ValueError(f"Lot introuvable (ID={lot_id}).")

        if not lot.est_actif:
            raise LotInactif(
                f"Le lot {lot.numero_lot} est inactif — ajustement impossible."
            )

        quantite_avant = lot.quantite_disponible

        # Calculer l'écart en pourcentage
        if quantite_avant > 0:
            ecart_pct = Decimal(str(abs((nouvelle_quantite - quantite_avant) / quantite_avant) * 100))
        else:
            ecart_pct = Decimal("100") if nouvelle_quantite != 0 else Decimal("0")

        if ecart_pct > self.SEUIL_ECART_APPROBATION:
            if not utilisateur.a_permission_role("pharmacien_adjoint"):
                raise EcartInventaireSignificatif(
                    f"Écart de {ecart_pct:.1f} % — approbation pharmacien adjoint requise.",
                    ecart_pct=ecart_pct,
                )

        # ── 3. Écriture DB ────────────────────────────────────────────────────
        with transaction.atomic():
            # Re-lock dans la transaction pour la cohérence
            lot = (
                Lot.objects
                .select_for_update()
                .filter(id=lot_id)
                .first()
            )
            lot.quantite_disponible = nouvelle_quantite
            lot.save(update_fields=["quantite_disponible"])

            ecart = nouvelle_quantite - quantite_avant
            from gestion.stocks.models import TypeMouvement
            type_mv = TypeMouvement.AJUSTEMENT_PLUS if ecart >= 0 else TypeMouvement.AJUSTEMENT_MOINS
            MouvementStock.objects.create(
                lot=lot,
                type_mouvement=type_mv,
                quantite=ecart,
                quantite_avant=quantite_avant,
                quantite_apres=nouvelle_quantite,
                motif=motif,
                effectue_par=utilisateur,
            )

            # CORRECTIF (audit 2026-07-21) : appel direct au journal d'audit,
            # dans la même transaction que l'ajustement — même pattern que
            # gestion.ventes.services.traiter_vente (§13). Auparavant, seul
            # un gestionnaire d'événement (_sur_stock_ajuste) existait pour
            # ce cas, mais aucun bus.publier() n'est jamais appelé en
            # production : l'ajustement n'était donc journalisé nulle part.
            # Volontairement PAS de publication sur le bus d'événements ici,
            # pour ne pas créer de double journalisation si le bus venait un
            # jour à être réellement câblé (cf. AUDIT §3.3).
            try:
                from gestion.audit.services import ServiceAudit
                ServiceAudit().journaliser_ajustement_stock(
                    lot=lot,
                    quantite_avant=quantite_avant,
                    quantite_apres=nouvelle_quantite,
                    motif=motif,
                    utilisateur=utilisateur,
                    adresse_ip=adresse_ip,
                )
            except Exception as exc:
                # Ne jamais bloquer un ajustement de stock à cause de l'audit.
                logger.warning(
                    "Audit : journalisation ajustement stock lot=%s échouée : %s",
                    lot.pk, exc,
                )

        logger.info("Stock ajusté : lot %s %d → %d", lot.numero_lot, quantite_avant, nouvelle_quantite)
        return lot

    # ─── Réception livraison ──────────────────────────────────────────────────

    def receptionner_livraison(
        self,
        bon_commande_id: uuid.UUID,
        lignes_reception: list,
        utilisateur,
    ) -> dict:
        """
        Réceptionne une livraison fournisseur : crée un ``Lot`` par ligne
        de bon de commande et journalise le mouvement ``ENTREE`` associé.

        Chaque élément de ``lignes_reception`` est un dict :

            {
                "medicament_id":         UUID,          # obligatoire
                "numero_lot":            str,           # obligatoire
                "date_peremption":       date,          # obligatoire
                "quantite":              int > 0,       # obligatoire
                "prix_achat_unitaire":   Decimal,       # obligatoire
                "date_fabrication":      date | None,   # optionnel
                "fournisseur":           str,           # optionnel
                "emplacement_stockage":  str,           # optionnel
                "notes":                 str,           # optionnel
            }

        La création des ``Lot`` et des ``MouvementStock`` est atomique :
        soit toutes les lignes sont écrites, soit aucune.

        Raises:
            PermissionRefusee: Si l'utilisateur n'est pas gestionnaire_stock+.
            ValueError:        Si une ligne est invalide (champ manquant,
                               quantité ≤ 0, médicament introuvable, etc.).
        """
        # ── 1. Permission (sans DB) ───────────────────────────────────────────
        if not utilisateur.a_permission_role("gestionnaire_stock"):
            raise PermissionRefusee(
                "La réception de livraison requiert au moins le rôle gestionnaire_stock."
            )

        if not lignes_reception:
            logger.info(
                "Livraison réceptionnée : bon %s — 0 lot(s) (rien à créer)",
                bon_commande_id,
            )
            return {"lots_crees": [], "nombre": 0}

        # ── 2. Validation stricte (avant toute écriture) ──────────────────────
        champs_obligatoires = (
            "medicament_id", "numero_lot", "date_peremption",
            "quantite", "prix_achat_unitaire",
        )
        for index, ligne in enumerate(lignes_reception):
            if not isinstance(ligne, dict):
                raise ValueError(
                    f"Ligne {index} invalide : un dict est attendu."
                )
            manquants = [c for c in champs_obligatoires if ligne.get(c) in (None, "")]
            if manquants:
                raise ValueError(
                    f"Ligne {index} incomplète — champs manquants : {manquants}."
                )
            try:
                quantite = int(ligne["quantite"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Ligne {index} : 'quantite' doit être un entier."
                ) from exc
            if quantite <= 0:
                raise ValueError(
                    f"Ligne {index} : 'quantite' doit être strictement positive."
                )

        # ── 3. Écriture DB atomique ───────────────────────────────────────────
        from gestion.stocks.models import TypeMouvement

        lots_crees: List = []
        with transaction.atomic():
            for ligne in lignes_reception:
                medicament = (
                    Medicament.objects
                    .select_for_update()
                    .filter(id=ligne["medicament_id"], est_actif=True)
                    .first()
                )
                if medicament is None:
                    raise ValueError(
                        f"Médicament introuvable ou inactif "
                        f"(ID={ligne['medicament_id']})."
                    )

                quantite = int(ligne["quantite"])
                prix_achat = Decimal(str(ligne["prix_achat_unitaire"]))

                lot = Lot.objects.create(
                    medicament=medicament,
                    numero_lot=ligne["numero_lot"],
                    numero_lot_interne=ligne.get("numero_lot_interne", "") or "",
                    date_fabrication=ligne.get("date_fabrication"),
                    date_peremption=ligne["date_peremption"],
                    quantite_initiale=quantite,
                    quantite_disponible=quantite,
                    prix_achat_unitaire=prix_achat,
                    fournisseur=ligne.get("fournisseur", "") or "",
                    bon_commande=str(bon_commande_id),
                    emplacement_stockage=ligne.get("emplacement_stockage", "") or "",
                    notes=ligne.get("notes", "") or "",
                )

                MouvementStock.objects.create(
                    lot=lot,
                    type_mouvement=TypeMouvement.RECEPTION,
                    quantite=quantite,
                    quantite_avant=0,
                    quantite_apres=quantite,
                    motif=f"Réception bon de commande {bon_commande_id}",
                    effectue_par=utilisateur,
                )
                lots_crees.append(lot)

        logger.info(
            "Livraison réceptionnée : bon %s — %d lot(s) créé(s)",
            bon_commande_id, len(lots_crees),
        )
        return {"lots_crees": lots_crees, "nombre": len(lots_crees)}

    # ─── Alertes ──────────────────────────────────────────────────────────────

    def verifier_alertes_stock(self) -> list:
        """
        Détecte les médicaments sous le seuil d'alerte.

        Returns:
            Liste d'AlerteStock créées ou mises à jour.
        """
        from django.db.models import Sum

        alertes = []
        medicaments = Medicament.objects.filter(est_actif=True).prefetch_related("lots")

        for medicament in medicaments:
            stock_total = (
                medicament.lots.filter(est_actif=True, quantite_disponible__gt=0)
                .aggregate(total=Sum("quantite_disponible"))["total"]
                or 0
            )

            if stock_total == 0:
                niveau = NiveauAlerte.RUPTURE
            elif stock_total <= medicament.seuil_alerte_stock:
                niveau = NiveauAlerte.ALERTE
            else:
                continue

            alerte, created = AlerteStock.objects.get_or_create(
                medicament=medicament,
                est_resolue=False,
                defaults={
                    "niveau": niveau,
                    "stock_au_moment_alerte": stock_total,
                    "seuil_depasse": medicament.seuil_alerte_stock,
                },
            )
            alertes.append(alerte)

        return alertes

    def calculer_besoins_reapprovisionnement(self) -> list:
        """
        Calcule les besoins de réapprovisionnement pour les médicaments sous alerte.

        Returns:
            Liste de dicts triés par urgence.
        """
        besoins = []
        alertes = self.verifier_alertes_stock()

        for alerte in alertes:
            besoins.append({
                "medicament": alerte.medicament,
                "stock_actuel": alerte.stock_au_moment_alerte,
                "seuil": alerte.seuil_depasse,
                "niveau": alerte.niveau,
            })

        return sorted(besoins, key=lambda b: b["stock_actuel"])

    # ─── Inventaire ───────────────────────────────────────────────────────────

    def enregistrer_comptage(
        self,
        inventaire_id: uuid.UUID,
        lot_id: uuid.UUID,
        quantite_comptee: int,
        utilisateur,
    ) -> "LigneInventaire":
        """
        Enregistre le comptage physique d'un lot dans un inventaire.

        Raises:
            PermissionRefusee: Si l'utilisateur n'est pas gestionnaire_stock+.
            ValueError: Si la quantité est négative, l'inventaire introuvable ou non en cours.
        """
        if not utilisateur.a_permission_role("gestionnaire_stock"):
            raise PermissionRefusee(
                "L'enregistrement de comptage requiert au moins le rôle gestionnaire_stock."
            )

        if quantite_comptee < 0:
            raise ValueError(
                f"La quantité comptée ne peut pas être négative (reçu : {quantite_comptee})."
            )

        inventaire = Inventaire.objects.filter(id=inventaire_id).first()
        if inventaire is None:
            raise ValueError(f"Inventaire introuvable (ID={inventaire_id}).")

        if inventaire.statut != "en_cours":
            raise ValueError(
                f"L'inventaire est au statut '{inventaire.statut}' — seul 'en_cours' est modifiable."
            )

        ligne, _ = LigneInventaire.objects.update_or_create(
            inventaire=inventaire,
            lot_id=lot_id,
            defaults={"quantite_comptee": quantite_comptee, "comptee_par": utilisateur},
        )
        return ligne

    def demarrer_inventaire(
        self,
        utilisateur,
        reference: str = "",
    ) -> "Inventaire":
        """Démarre un inventaire physique.

        Raises:
            PermissionRefusee: Si l'utilisateur n'est pas gestionnaire_stock+.
        """
        if not utilisateur.a_permission_role("gestionnaire_stock"):
            raise PermissionRefusee(
                "Le démarrage d'inventaire requiert au moins le rôle gestionnaire_stock."
            )
        return Inventaire.objects.create(
            reference=reference,
            demarre_par=utilisateur,
        )
