"""
gestion/ventes/avoir.py — Étape 14

ServiceAvoir : Génération d'un avoir (note de crédit) suite à un retour produit.

Un avoir :
  - Référence la vente d'origine via Vente.vente_origine (FK)
  - Est représenté comme une Vente avec statut=AVOIR et montant_total négatif
  - Remet en stock les lots d'origine (MouvementStock RETOUR_CLIENT)
  - Crée une EcritureComptable de type AVOIR
  - S'inscrit dans l'Outbox pour synchronisation cloud
  - Est imprimable via le template reçu (mention AVOIR)

Règles métier :
  - Un avoir est possible MÊME après clôture (contrairement à l'annulation).
  - Le motif est obligatoire.
  - La vente d'origine doit être VALIDEE (pas déjà annulée ou avoir).
  - Les quantités retournées ne peuvent pas dépasser les quantités vendues.
"""

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from gestion.exceptions import PermissionRefusee
from gestion.ventes.models import Vente, LigneVente, StatutVente
from gestion.catalogue.models import Lot
from gestion.stocks.models import MouvementStock, TypeMouvement
from gestion.parametrage.models import (
    CompteurNumerotation, TypeCompteur, appliquer_format_numero, Parametrage
)
from gestion.ordonnances.models import Ordonnance, StatutOrdonnance

logger = logging.getLogger("pharmapp.ventes.avoir")


class ServiceAvoir:
    """Service métier pour la création d'avoirs (retours produits)."""

    def creer_avoir(
        self,
        vente_origine_id: uuid.UUID,
        lignes_retour: list,
        motif: str,
        utilisateur,
        adresse_ip: str = "",
    ) -> Vente:
        """
        Crée un avoir pour une vente existante.

        Args:
            vente_origine_id: UUID de la vente d'origine.
            lignes_retour: Liste de dicts {"ligne_id": uuid, "quantite": int}.
            motif: Raison du retour (obligatoire).
            utilisateur: Utilisateur qui effectue l'avoir.
            adresse_ip: IP pour l'audit.

        Returns:
            La Vente de type AVOIR créée.

        Raises:
            PermissionRefusee: Si niveau < pharmacien_adjoint.
            ValueError: Vente introuvable, déjà annulée, quantités invalides.
        """
        if not utilisateur.a_permission_role("pharmacien_adjoint"):
            raise PermissionRefusee(
                "La création d'un avoir requiert au moins le rôle pharmacien_adjoint."
            )

        if not motif or not motif.strip():
            raise ValueError("Le motif de l'avoir est obligatoire.")

        if not lignes_retour:
            raise ValueError("Aucune ligne à retourner.")

        with transaction.atomic():
            # ── 1. Récupérer et verrouiller la vente d'origine ───────────────
            vente_origine = (
                Vente.objects
                .select_for_update()
                .filter(id=vente_origine_id)
                .first()
            )
            if vente_origine is None:
                raise ValueError(f"Vente introuvable (ID={vente_origine_id}).")

            if vente_origine.statut == StatutVente.ANNULEE:
                raise ValueError("Impossible de créer un avoir sur une vente annulée.")

            if vente_origine.statut == StatutVente.AVOIR:
                raise ValueError("Impossible de créer un avoir sur un avoir existant.")

            # ── 2. Résolution et validation des lignes à retourner ─────────────
            lignes_vente = {
                str(l.id): l
                for l in vente_origine.lignes.select_related("lot__medicament").all()
            }

            lignes_traitees = []
            total_avoir = Decimal("0.00")

            for item in lignes_retour:
                ligne_id = str(item.get("ligne_id", ""))
                quantite_retour = int(item.get("quantite", 0))

                if ligne_id not in lignes_vente:
                    raise ValueError(
                        f"La ligne {ligne_id} n'appartient pas à la vente {vente_origine.numero}."
                    )

                ligne = lignes_vente[ligne_id]
                if quantite_retour <= 0 or quantite_retour > ligne.quantite:
                    raise ValueError(
                        f"Quantité invalide pour la ligne {ligne_id} : "
                        f"vendu={ligne.quantite}, retourné={quantite_retour}."
                    )

                montant_ligne = ligne.prix_unitaire_apres_remise * quantite_retour
                total_avoir += montant_ligne
                lignes_traitees.append({
                    "ligne": ligne,
                    "quantite_retour": quantite_retour,
                    "montant_ligne": montant_ligne,
                })

            if total_avoir <= 0:
                raise ValueError("Le montant total de l'avoir doit être positif.")

            # ── 3. Génération du numéro d'avoir ───────────────────────────────
            now = timezone.now()
            annee = now.year
            mois = now.month
            compteur, _ = CompteurNumerotation.objects.select_for_update().get_or_create(
                type=TypeCompteur.AVOIR if hasattr(TypeCompteur, 'AVOIR') else "avoir",
                annee=annee,
                defaults={"sequence": 0},
            )
            compteur.sequence += 1
            compteur.save(update_fields=["sequence"])

            param = Parametrage.obtenir()
            # Gabarit avoir : remplace VENTE par AV
            gabarit = getattr(param, "format_numerotation", "VTE-{YYYY}-{NNNN}")
            gabarit_avoir = gabarit.replace("VTE", "AV").replace("vte", "av")
            numero_avoir = appliquer_format_numero(gabarit_avoir, annee, mois, compteur.sequence)

            # ── 4. Création de la Vente AVOIR ─────────────────────────────────
            vente_avoir = Vente.objects.create(
                numero=numero_avoir,
                vendeur=utilisateur,
                client=vente_origine.client,
                ordonnance=vente_origine.ordonnance,
                statut=StatutVente.AVOIR,
                mode_paiement=vente_origine.mode_paiement,
                sous_total=-total_avoir,
                montant_total=-total_avoir,
                montant_encaisse=-total_avoir,
                montant_rendu=Decimal("0.00"),
                vente_origine=vente_origine,
                notes=(
                    f"Avoir sur vente {vente_origine.numero}. "
                    f"Motif : {motif.strip()}"
                ),
            )

            # ── 5. Lignes d'avoir + remise en stock ───────────────────────────
            for item in lignes_traitees:
                ligne: LigneVente = item["ligne"]
                qte: int = item["quantite_retour"]
                montant: Decimal = item["montant_ligne"]

                # Créer ligne d'avoir (quantité positive dans l'avoir)
                LigneVente.objects.create(
                    vente=vente_avoir,
                    medicament=ligne.medicament,
                    lot=ligne.lot,
                    quantite=qte,
                    prix_unitaire=ligne.prix_unitaire,
                    taux_remise=ligne.taux_remise,
                    prix_unitaire_apres_remise=ligne.prix_unitaire_apres_remise,
                    montant_total=montant,
                )

                # Remettre le stock dans le lot d'origine
                if ligne.lot_id:
                    lot = Lot.objects.select_for_update().get(id=ligne.lot_id)
                    quantite_avant = lot.quantite_disponible
                    lot.quantite_disponible += qte
                    lot.save(update_fields=["quantite_disponible"])

                    MouvementStock.objects.create(
                        lot=lot,
                        type_mouvement=TypeMouvement.RETOUR_CLIENT,
                        quantite=qte,
                        quantite_avant=quantite_avant,
                        quantite_apres=lot.quantite_disponible,
                        motif=f"Avoir {numero_avoir} — {motif.strip()[:100]}",
                        effectue_par=utilisateur,
                    )

            # ── 6. Écriture comptable AVOIR ────────────────────────────────────
            try:
                from gestion.comptabilite.models import EcritureComptable
                EcritureComptable.objects.create(
                    type="avoir",
                    vente=vente_avoir,
                    montant=-total_avoir,
                    reference=numero_avoir,
                    notes=f"Avoir sur {vente_origine.numero}",
                    effectue_par=utilisateur,
                )
            except Exception as exc:
                # La comptabilité ne bloque pas l'avoir
                logger.warning("Impossible de créer l'écriture comptable pour l'avoir %s : %s", numero_avoir, exc)

            # ── 7. Audit ──────────────────────────────────────────────────────
            try:
                from gestion.audit.services import ServiceAudit
                ServiceAudit.enregistrer(
                    utilisateur=utilisateur,
                    action="avoir_cree",
                    ressource="vente",
                    ressource_id=str(vente_avoir.id),
                    details={
                        "avoir_numero": numero_avoir,
                        "vente_origine": vente_origine.numero,
                        "motif": motif.strip(),
                        "total_avoir": str(total_avoir),
                        "lignes": [
                            {
                                "medicament": item["ligne"].medicament.nom,
                                "quantite": item["quantite_retour"],
                                "montant": str(item["montant_ligne"]),
                            }
                            for item in lignes_traitees
                        ],
                    },
                    adresse_ip=adresse_ip,
                    niveau_criticite="WARNING",
                )
            except Exception as exc:
                logger.warning("Audit avoir %s non enregistré : %s", numero_avoir, exc)

            # ── 8. Outbox pour synchronisation cloud ──────────────────────────
            try:
                from infrastructure.outbox.modeles import EntreeOutbox
                EntreeOutbox.objects.create(
                    type_evenement="EvenementAvoirCree",
                    id_objet=vente_avoir.id,
                    charge_utile={
                        "avoir_id": str(vente_avoir.id),
                        "avoir_numero": numero_avoir,
                        "vente_origine_id": str(vente_origine.id),
                        "vente_origine_numero": vente_origine.numero,
                        "total_avoir": str(total_avoir),
                        "motif": motif.strip(),
                        "effectue_par": str(utilisateur.id),
                    },
                )
            except Exception as exc:
                logger.warning("Outbox avoir %s non inscrite : %s", numero_avoir, exc)

            # ── 9. Restitution de l'ordonnance (si toutes les lignes retournées) ─
            # Si la vente d'origine avait une ordonnance et que l'avoir couvre
            # l'intégralité du montant (retour total), l'ordonnance repasse au
            # statut VALIDEE pour permettre une nouvelle dispensation conforme.
            if vente_origine.ordonnance is not None and total_avoir >= abs(vente_origine.montant_total):
                try:
                    from gestion.ordonnances.models import StatutOrdonnance
                    ord_ = vente_origine.ordonnance
                    if ord_.statut == StatutOrdonnance.UTILISEE:
                        ord_.statut = StatutOrdonnance.VALIDEE
                        ord_.save(update_fields=["statut", "modifie_le"])
                        logger.info(
                            "ordonnance_reactivee: %s suite avoir %s (retour total)",
                            ord_.id, numero_avoir,
                        )
                except Exception as exc:
                    logger.warning(
                        "Impossible de réactiver l'ordonnance pour l'avoir %s : %s",
                        numero_avoir, exc,
                    )

            logger.info(
                "avoir_cree: %s → vente_origine=%s total=%s FCFA",
                numero_avoir,
                vente_origine.numero,
                total_avoir,
            )
            return vente_avoir
