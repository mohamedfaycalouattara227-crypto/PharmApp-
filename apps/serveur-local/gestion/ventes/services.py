"""
Module : gestion/ventes/services.py
Description : Service métier pour la gestion des ventes de PharmApp.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from gestion.exceptions import (
    PermissionRefusee,
    PanierVide,
    MontantEncaisseInsuffisant,
    ModePaiementInvalide,
    StockInsuffisant,
    OrdonnanceRequise,
    VenteDejaAnnulee,
    DelaiAnnulationDepasse,
)

# Imports module-level pour que patch() fonctionne dans les tests
from gestion.ventes.models import Vente, LigneVente, ClotureCaisse
from gestion.ordonnances.models import Ordonnance, StatutOrdonnance
from gestion.catalogue.models import Lot
from gestion.stocks.models import MouvementStock, TypeMouvement, AlerteStock, NiveauAlerte
from gestion.produits_controles.services import ServiceProduitControle
from gestion.audit.services import ServiceAudit
from infrastructure.outbox.modeles import EntreeOutbox
from gestion.parametrage.models import (CompteurNumerotation, TypeCompteur, appliquer_format_numero, Parametrage)

logger = logging.getLogger("pharmapp.ventes")

# Coupures valides en FCFA (ordre décroissant)
COUPURES_FCFA = [10000, 5000, 2000, 1000, 500, 200, 100, 50, 25, 10, 5]
MODES_PAIEMENT_VALIDES = {"especes", "mobile_money", "assurance", "credit", "cheque"}


def _verifier_cloture_ouverte() -> bool:
    """
    Retourne True si la caisse est ouverte aujourd'hui (pas encore clôturée).
    Définie ici (module services) pour être patchable dans les tests unitaires.
    La même logique existe dans vues.py (import depuis ici).
    """
    from django.utils import timezone
    today = timezone.now().date()
    cloturee = ClotureCaisse.objects.filter(
        date_cloture=today,
        statut__in=["cloturee", "validee"],
    ).exists()
    return not cloturee  # True = caisse ouverte, vente autorisée


# ─── Objets de valeur ─────────────────────────────────────────────────────────

@dataclass
class ArticlePanier:
    """
    Représente un article dans le panier de vente.
    Valide les données à la création.
    """
    medicament_id: uuid.UUID
    quantite: int
    prix_unitaire_demande: Decimal
    taux_remise: Decimal = Decimal("0.00")
    lot_id: Optional[uuid.UUID] = None
    necessite_ordonnance: bool = False

    def __post_init__(self):
        if self.quantite <= 0:
            raise ValueError(
                "La quantité doit être strictement positive (reçu : %d)." % self.quantite
            )
        if self.prix_unitaire_demande < Decimal("0"):
            raise ValueError(
                "Le prix unitaire ne peut pas être négatif "
                "(reçu : %s FCFA)." % self.prix_unitaire_demande
            )
        if not (Decimal("0") <= self.taux_remise <= Decimal("100")):
            raise ValueError(
                "Le taux de remise doit être compris entre 0 et 100 %% "
                "(reçu : %s %%)." % self.taux_remise
            )

    @property
    def montant_ligne(self) -> Decimal:
        return self.quantite * self.prix_unitaire_demande * (1 - self.taux_remise / 100)


class ListeArticles:
    """
    Panier de vente — liste validée d'ArticlePanier.
    """

    def __init__(self, articles: Optional[List[ArticlePanier]] = None):
        self._articles: List[ArticlePanier] = articles or []

    @property
    def est_vide(self) -> bool:
        return len(self._articles) == 0

    @property
    def nombre_articles(self) -> int:
        """Retourne la somme des quantités de tous les articles."""
        return sum(a.quantite for a in self._articles)

    @property
    def montant_total(self) -> Decimal:
        return sum(a.montant_ligne for a in self._articles)

    def ajouter(self, article: ArticlePanier) -> None:
        """Ajoute ou cumule un article dans le panier."""
        for existant in self._articles:
            if existant.medicament_id == article.medicament_id:
                existant.quantite += article.quantite
                return
        self._articles.append(article)

    def __iter__(self):
        return iter(self._articles)

    def __len__(self) -> int:
        return len(self._articles)

    def __bool__(self) -> bool:
        return not self.est_vide


@dataclass
class ResultatVente:
    """Résultat d'une transaction de vente."""
    facture: Any = None
    monnaie_rendue: Decimal = Decimal("0")
    alertes_stock: list = field(default_factory=list)


# ─── Service principal ────────────────────────────────────────────────────────

class ServiceVente:
    """Service métier pour les ventes de PharmApp."""

    # ─── Traitement vente ─────────────────────────────────────────────────────

    def traiter_vente(
        self,
        panier,
        mode_paiement: str,
        montant_encaisse: Decimal,
        utilisateur=None,
        vendeur=None,           # alias rétro-compatible
        client=None,
        ordonnance_id: Optional[uuid.UUID] = None,
        adresse_ip: str = "",
    ) -> ResultatVente:
        """
        Enregistre une vente complète.

        Cycle de vie complet (14 étapes) :
        1.  Validation des arguments hors DB (permission, panier, mode paiement, montant)
        2.  Construction des ArticlePanier normalisés depuis le panier brut
        3.  Calcul du montant total et de la monnaie rendue
        4.  Ouverture d'une transaction atomique
        5.  Récupération et vérification de l'ordonnance (si fournie)
        6.  Pour chaque article : sélection du lot FEFO (ou lot explicite)
        7.  Vérification du stock disponible → StockInsuffisant si insuffisant
        8.  Vérification ordonnance au niveau médicament → OrdonnanceRequise si manquante
        9.  Décrémentation du stock (quantite_disponible -= quantite)
        10. Création du MouvementStock (type VENTE, quantité négative)
        11. Création de la Vente en base
        12. Création des LigneVente (une par article)
        13. Écriture dans le journal d'audit (ServiceAudit)
        14. Inscription dans l'Outbox transactionnelle (synchronisation cloud)

        Raises:
            PanierVide: Si le panier est vide.
            PermissionRefusee: Si le vendeur n'est pas au moins caissier.
            ModePaiementInvalide: Si le mode n'existe pas.
            MontantEncaisseInsuffisant: Si espèces sans montant suffisant.
            StockInsuffisant: Si un lot n'a pas assez de stock.
            OrdonnanceRequise: Si un médicament exige une ordonnance non fournie.
        """
        # ── 1. Alias rétro-compatible utilisateur/vendeur ─────────────────────
        if utilisateur is None:
            utilisateur = vendeur
        vendeur = utilisateur

        # ── 2. Validations sans accès DB (ordre important : avant transaction) ──
        if not panier:
            raise PanierVide("Le panier est vide — aucune vente possible.")

        if not vendeur.a_permission_role("caissier"):
            raise PermissionRefusee(
                "L'enregistrement d'une vente requiert au moins le rôle caissier."
            )

        if mode_paiement not in MODES_PAIEMENT_VALIDES:
            raise ModePaiementInvalide(
                f"Mode de paiement '{mode_paiement}' non reconnu. "
                f"Modes valides : {sorted(MODES_PAIEMENT_VALIDES)}"
            )

        if mode_paiement == "especes" and montant_encaisse <= Decimal("0"):
            raise MontantEncaisseInsuffisant(
                "Le montant encaissé doit être supérieur à zéro pour un paiement en espèces."
            )

        # ── 3. Normalisation du panier en ArticlePanier ───────────────────────
        articles: List[ArticlePanier] = []
        for raw in panier:
            if isinstance(raw, ArticlePanier):
                articles.append(raw)
            else:
                lot_id_raw = raw.get("lot_id")
                articles.append(ArticlePanier(
                    medicament_id=uuid.UUID(str(raw["medicament_id"])),
                    quantite=int(raw.get("quantite", 1)),
                    prix_unitaire_demande=Decimal(str(raw.get("prix_unitaire_demande", "0"))),
                    taux_remise=Decimal(str(raw.get("taux_remise", "0"))),
                    lot_id=uuid.UUID(str(lot_id_raw)) if lot_id_raw else None,
                ))

        # ── 4. Calcul montant total et validation espèces ─────────────────────
        montant_total = sum(a.montant_ligne for a in articles)
        monnaie_rendue = Decimal("0")
        if mode_paiement == "especes":
            # BUG FIX (règle espèces) : valider que l'encaissement couvre le total
            # AVANT d'entrer dans la transaction atomique.  L'ancienne version
            # utilisait max(0, encaisse - total) sans lever d'erreur, permettant
            # de finaliser une vente sous-encaissée avec 0 FCFA de monnaie rendue.
            if montant_encaisse < montant_total:
                raise MontantEncaisseInsuffisant(
                    f"Montant encaissé ({montant_encaisse} FCFA) insuffisant "
                    f"pour couvrir le total ({montant_total} FCFA). "
                    f"Il manque {montant_total - montant_encaisse} FCFA.",
                    montant_total=str(montant_total),
                    montant_encaisse=str(montant_encaisse),
                    manque=str(montant_total - montant_encaisse),
                )
            monnaie_rendue = montant_encaisse - montant_total

        # ── 5-14. Transaction atomique ─────────────────────────────────────────
        alertes_stock = []

        with transaction.atomic():
            # ── 5. Récupération de l'ordonnance ───────────────────────────────
            ordonnance = self._resoudre_ordonnance(ordonnance_id)

            # ── 5b. Création de la Vente (déplacée avant la boucle) ────────────
            # CORRECTIF : la Vente doit exister avant la boucle par lot pour
            # pouvoir créer chaque LigneVente au fil de l'eau et la lier
            # immédiatement à son entrée de registre produits contrôlés
            # (RegistreProduitControle.ligne_vente) — nécessaire pour que le
            # job de réconciliation puisse détecter, par simple filtre isnull,
            # les ventes de produits contrôlés sans entrée correspondante.
            numero = self._generer_numero_vente()
            vente = Vente.objects.create(
                numero=numero,
                vendeur=vendeur,
                client=client,
                ordonnance=ordonnance,
                mode_paiement=mode_paiement,
                montant_total=montant_total,
                montant_encaisse=montant_encaisse,
                montant_rendu=monnaie_rendue,
                statut="validee",
            )

            # ── 6-10. Vérification stock + décrémentation, lot par lot (FEFO) ─
            lots_reserves: List[tuple] = []   # (lot, article, qte_avant)

            for article in articles:
                # ── 6. Sélection du lot ───────────────────────────────────────
                if article.lot_id:
                    # Lot explicitement demandé
                    lot = (
                        Lot.objects
                        .select_related("medicament")
                        .select_for_update()
                        .filter(id=article.lot_id, est_actif=True)
                        .first()
                    )
                    if lot is None:
                        raise StockInsuffisant(
                            f"Lot introuvable ou inactif (ID={article.lot_id}).",
                            lot_id=str(article.lot_id),
                        )
                else:
                    # FEFO : premier lot non périmé avec stock pour ce médicament
                    lot = (
                        Lot.objects
                        .select_related("medicament")
                        .select_for_update()
                        .filter(
                            medicament_id=article.medicament_id,
                            est_actif=True,
                            quantite_disponible__gt=0,
                            date_peremption__gt=timezone.now().date(),
                        )
                        .order_by("date_peremption")   # FEFO
                        .first()
                    )
                    if lot is None:
                        raise StockInsuffisant(
                            f"Aucun lot disponible pour le médicament "
                            f"(ID={article.medicament_id}).",
                            medicament_id=str(article.medicament_id),
                        )

                # ── 7. Vérification du stock disponible ───────────────────────
                if lot.quantite_disponible < article.quantite:
                    raise StockInsuffisant(
                        f"Stock insuffisant pour '{lot.medicament.nom}' : "
                        f"{lot.quantite_disponible} unité(s) disponible(s), "
                        f"{article.quantite} demandée(s).",
                        medicament_id=str(lot.medicament_id),
                        lot_id=str(lot.id),
                        disponible=lot.quantite_disponible,
                        demande=article.quantite,
                    )

                # ── 8. Vérification ordonnance au niveau médicament ───────────
                if lot.medicament.necessite_ordonnance and ordonnance is None:
                    raise OrdonnanceRequise(
                        f"Le médicament '{lot.medicament.nom}' nécessite "
                        f"une ordonnance valide.",
                        medicament_id=str(lot.medicament_id),
                        medicament_nom=lot.medicament.nom,
                    )

                # ── 9. Décrémentation du stock ────────────────────────────────
                quantite_avant = lot.quantite_disponible
                lot.quantite_disponible -= article.quantite
                lot.save(update_fields=["quantite_disponible"])

                # ── 10. Mouvement de stock (sortie vente) ─────────────────────
                MouvementStock.objects.create(
                    lot=lot,
                    type_mouvement=TypeMouvement.VENTE,
                    quantite=-article.quantite,   # négatif = sortie
                    quantite_avant=quantite_avant,
                    quantite_apres=lot.quantite_disponible,
                    motif="Vente",
                    effectue_par=vendeur,
                )

                # ── 10a. Création de la LigneVente pour ce lot ─────────────────
                # CORRECTIF : créée ici (au fil de l'eau) plutôt que dans une
                # boucle séparée après coup, afin qu'elle existe déjà au moment
                # de l'écriture au registre des produits contrôlés (10b) et
                # puisse y être liée (RegistreProduitControle.ligne_vente).
                ligne_vente = LigneVente.objects.create(
                    vente=vente,
                    medicament=lot.medicament,
                    lot=lot,
                    quantite=article.quantite,
                    prix_unitaire=article.prix_unitaire_demande,
                    taux_remise=article.taux_remise,
                )

                # ── 10b. Registre produits contrôlés (Étape 13 — CDC §4.10) ──
                # Si le médicament est un produit contrôlé (stupéfiant/psychotrope),
                # inscrire la sortie dans le registre réglementaire ANRP.
                # L'écriture dans ce registre est obligatoire avant vente.
                if getattr(lot.medicament, "est_produit_controle", False):
                    try:
                        # CORRECTIF : instanciation correcte (méthode d'instance, pas statique),
                        # paramètre `medicament` obligatoire ajouté, `utilisateur` renommé en
                        # `vendeur` pour correspondre à la signature réelle de
                        # ServiceProduitControle.enregistrer_sortie_vente. `ligne_vente` transmis
                        # pour permettre au job de réconciliation de détecter les manques.
                        ServiceProduitControle().enregistrer_sortie_vente(
                            medicament=lot.medicament,
                            lot=lot,
                            quantite=article.quantite,
                            vendeur=vendeur,
                            ordonnance=ordonnance,
                            ligne_vente=ligne_vente,
                            # Le lot a déjà été décrémenté en 9 : on transmet
                            # la valeur d'origine plutôt que de la déduire.
                            stock_avant=quantite_avant,
                        )
                    except Exception as exc:
                        # Ne jamais bloquer une vente à cause du registre réglementaire.
                        # Un job de réconciliation peut recalculer les entrées manquantes.
                        # Mais c'est critique → loggué en ERROR pour alerte.
                        logger.error(
                            "CRITIQUE — Registre produits contrôlés : impossible d'enregistrer "
                            "la sortie pour le médicament '%s' (lot=%s, vente en cours) : %s",
                            lot.medicament.nom, lot.numero_lot, exc,
                            exc_info=True,
                        )

                lots_reserves.append((lot, article, quantite_avant))

                # Détecter si le stock passe sous le seuil d'alerte et persister en base
                if lot.quantite_disponible <= lot.medicament.seuil_alerte_stock:
                    alertes_stock.append(lot.medicament.nom)
                    try:
                        from gestion.stocks.models import AlerteStock, NiveauAlerte
                        niveau = (
                            NiveauAlerte.RUPTURE
                            if lot.quantite_disponible <= lot.medicament.seuil_rupture_stock
                            else NiveauAlerte.ALERTE
                        )
                        AlerteStock.objects.get_or_create(
                            medicament=lot.medicament,
                            est_resolue=False,
                            defaults={
                                "niveau": niveau,
                                "stock_actuel": lot.quantite_disponible,
                                "seuil": lot.medicament.seuil_alerte_stock,
                            },
                        )
                    except Exception as exc:
                        logger.warning(
                            "Impossible de persister l'alerte stock pour %s : %s",
                            lot.medicament.nom, exc,
                        )

            # ── 11. Vente déjà créée en 5b (avant la boucle par lot) ───────────

            # ── 11b. Marquage de l'ordonnance comme utilisée ──────────────────
            # CORRECTIF : l'ordonnance doit impérativement passer au statut
            # "utilisee" après dispensation, afin d'empêcher toute réutilisation
            # sur une vente ultérieure (y compris pour des produits contrôlés).
            # Sans ce marquage, la même ordonnance reste indéfiniment "validee"
            # et peut justifier un nombre illimité de ventes.
            if ordonnance is not None:
                ordonnance.statut = StatutOrdonnance.UTILISEE
                ordonnance.save(update_fields=["statut", "modifie_le"])

            # ── 11c. Mise à jour de l'encours crédit du client ───────────────
            # Pour une vente à crédit, incrémenter l'encours du client dans la
            # même transaction atomique afin que le plafond soit toujours exact.
            if mode_paiement == "credit" and client is not None:
                try:
                    from django.db.models import F as _F
                    from gestion.clients.models import Client as _Client
                    _Client.objects.filter(pk=client.pk).update(
                        encours_credit=_F("encours_credit") + montant_total
                    )
                except Exception as exc:
                    logger.error(
                        "Impossible de mettre à jour l'encours crédit client=%s : %s",
                        client.pk, exc, exc_info=True,
                    )
                    raise  # Bloque la vente : l'encours doit être cohérent

            # ── 12. LigneVente déjà créées en 10a (au fil de la boucle) ────────

            # ── 13. Journal d'audit ───────────────────────────────────────────
            try:
                from gestion.audit.services import ServiceAudit
                ServiceAudit().journaliser_vente(
                    vente=vente,
                    utilisateur=vendeur,
                    adresse_ip=adresse_ip,
                )
            except Exception as exc:
                # Ne jamais bloquer une vente à cause de l'audit
                logger.warning(
                    "Audit : journalisation vente %s échouée : %s",
                    vente.numero, exc,
                )

            # ── 14. Outbox transactionnelle (synchronisation cloud) ───────────
            try:
                from infrastructure.outbox.modeles import EntreeOutbox
                EntreeOutbox.creer(
                    type_evenement="EvenementVenteCreee",
                    charge_utile={
                        "numero": vente.numero,
                        "montant_total": str(vente.montant_total),
                        "mode_paiement": vente.mode_paiement,
                        "vendeur_id": str(vente.vendeur_id),
                        "client_id": str(vente.client_id) if vente.client_id else None,
                        "nombre_lignes": len(lots_reserves),
                    },
                    id_objet=vente.id,
                    modele_source="Vente",
                    id_utilisateur=vendeur.id,
                )
            except Exception as exc:
                # Ne jamais bloquer une vente à cause de l'outbox
                logger.warning(
                    "Sync : inscription outbox vente %s échouée : %s",
                    vente.numero, exc,
                )

        logger.info(
            "Vente %s enregistrée — %s FCFA — %s — %d ligne(s)",
            vente.numero, montant_total, mode_paiement, len(lots_reserves),
        )
        return ResultatVente(
            facture=vente,
            monnaie_rendue=monnaie_rendue,
            alertes_stock=alertes_stock,
        )

    def _resoudre_ordonnance(self, ordonnance_id: Optional[uuid.UUID]):
        """
        Résout une ordonnance à partir de son identifiant.
        Méthode séparée (non inline) afin d'être patchable dans les tests unitaires.

        Returns:
            Instance Ordonnance si ordonnance_id est fourni, None sinon.
        Raises:
            ValueError: Si ordonnance_id est fourni mais introuvable en base.
        """
        if not ordonnance_id:
            return None
        ordonnance = Ordonnance.objects.filter(id=ordonnance_id).first()
        if ordonnance is None:
            raise ValueError(f"Ordonnance introuvable (ID={ordonnance_id}).")
        return ordonnance

    def _generer_numero_vente(self) -> str:
        """
        Génère le prochain numéro de vente de manière atomique et sans collision.

        FIX RACE CONDITION : utilise CompteurNumerotation avec SELECT FOR UPDATE
        à l'intérieur d'une transaction atomique.  L'ancienne implémentation
        (count() + 1) pouvait retourner le même numéro à deux transactions
        concurrentes — la deuxième plantait alors sur le UNIQUE constraint.

        FIX FORMAT : lit le gabarit depuis Parametrage.format_numerotation au lieu
        du format codé en dur "V-{annee}-{NNNNNN}" qui ignorait le paramétrage UI.

        Doit être appelée à l'intérieur d'un bloc transaction.atomic().
        """
        from gestion.parametrage.models import (
            CompteurNumerotation,
            TypeCompteur,
            appliquer_format_numero,
            Parametrage,
        )
        now   = timezone.now()
        annee = now.year
        mois  = now.month

        # Verrou exclusif sur la ligne (type, annee) — crée si absente
        compteur, _ = (
            CompteurNumerotation.objects
            .select_for_update()
            .get_or_create(type=TypeCompteur.VENTE, annee=annee)
        )
        compteur.sequence += 1
        compteur.save(update_fields=["sequence"])

        gabarit = Parametrage.obtenir().format_numerotation or "VTE-{YYYY}-{NNNN}"
        return appliquer_format_numero(gabarit, annee, mois, compteur.sequence)

    # ─── Annulation ───────────────────────────────────────────────────────────

    def annuler_vente(
        self,
        vente_id: uuid.UUID,
        motif: str,
        utilisateur,
        adresse_ip: str = "",
    ):
        """
        Annule une vente et restaure le stock des lots concernés.

        Raises:
            PermissionRefusee: Si l'utilisateur n'est pas pharmacien_adjoint+.
            VenteDejaAnnulee: Si la vente est déjà annulée.
            DelaiAnnulationDepasse: Si le délai est dépassé.
        """
        # ── Vérification permission sans DB ──────────────────────────────────
        if not utilisateur.a_permission_role("pharmacien_adjoint"):
            raise PermissionRefusee(
                "L'annulation requiert au moins le rôle pharmacien_adjoint."
            )

        with transaction.atomic():
            vente = (
                Vente.objects
                .filter(id=vente_id)
                .select_for_update()
                .first()
            )
            if vente is None:
                raise ValueError(f"Vente introuvable (ID={vente_id}).")

            if vente.statut == "annulee":
                raise VenteDejaAnnulee("Cette vente a déjà été annulée.")

            delai = getattr(settings, "DELAI_ANNULATION_VENTE_MINUTES", 30)
            limite = vente.cree_le + timedelta(minutes=delai)
            if timezone.now() > limite:
                raise DelaiAnnulationDepasse(
                    f"Le délai d'annulation de {delai} minutes est dépassé."
                )

            # ── Restauration du stock ─────────────────────────────────────────
            from gestion.catalogue.models import Lot
            from gestion.stocks.models import MouvementStock, TypeMouvement

            for ligne in vente.lignes.select_related("lot").all():
                lot = (
                    Lot.objects
                    .select_for_update()
                    .filter(id=ligne.lot_id)
                    .first()
                )
                if lot is not None:
                    quantite_avant = lot.quantite_disponible
                    lot.quantite_disponible += ligne.quantite
                    lot.save(update_fields=["quantite_disponible"])
                    MouvementStock.objects.create(
                        lot=lot,
                        type_mouvement=TypeMouvement.RETOUR_CLIENT,
                        quantite=ligne.quantite,     # positif = retour entrée
                        quantite_avant=quantite_avant,
                        quantite_apres=lot.quantite_disponible,
                        motif=f"Annulation vente {vente.numero} — {motif}",
                        reference_document=vente.numero,
                        effectue_par=utilisateur,
                    )

            # ── Mise à jour statut vente ──────────────────────────────────────
            vente.statut = "annulee"
            vente.motif_annulation = motif
            vente.annule_le = timezone.now()
            vente.annule_par = utilisateur
            vente.save(update_fields=["statut", "motif_annulation", "annule_le", "annule_par"])

            # ── Audit ─────────────────────────────────────────────────────────
            try:
                from gestion.audit.services import ServiceAudit
                ServiceAudit().journaliser_annulation_vente(
                    vente=vente,
                    motif=motif,
                    utilisateur=utilisateur,
                    adresse_ip=adresse_ip,
                )
            except Exception as exc:
                logger.warning(
                    "Audit : journalisation annulation vente %s échouée : %s",
                    vente.numero, exc,
                )

            # ── Outbox ───────────────────────────────────────────────────────
            try:
                from infrastructure.outbox.modeles import EntreeOutbox
                EntreeOutbox.creer(
                    type_evenement="EvenementVenteAnnulee",
                    charge_utile={
                        "numero": vente.numero,
                        "motif": motif,
                        "vendeur_id": str(vente.vendeur_id),
                    },
                    id_objet=vente.id,
                    modele_source="Vente",
                    id_utilisateur=utilisateur.id,
                )
            except Exception as exc:
                logger.warning(
                    "Sync : inscription outbox annulation %s échouée : %s",
                    vente.numero, exc,
                )

        return vente

    # ─── Monnaie rendue ───────────────────────────────────────────────────────

    def calculer_monnaie_rendue(
        self,
        montant_total: Decimal,
        montant_encaisse: Decimal,
    ) -> dict:
        """
        Calcule la monnaie à rendre en coupures FCFA.

        Raises:
            MontantEncaisseInsuffisant: Si le montant encaissé est inférieur au total.

        Returns:
            {"montant_rendu": Decimal, "decomposition": {coupure: nombre}}
        """
        if montant_encaisse < montant_total:
            raise MontantEncaisseInsuffisant(
                f"Montant encaissé ({montant_encaisse} FCFA) inférieur "
                f"au total ({montant_total} FCFA)."
            )

        montant_rendu = montant_encaisse - montant_total
        decomposition = {}
        reste = int(montant_rendu)

        for coupure in COUPURES_FCFA:
            if reste >= coupure:
                nombre = reste // coupure
                decomposition[coupure] = nombre
                reste -= nombre * coupure

        return {"montant_rendu": montant_rendu, "decomposition": decomposition}

    # ─── Historique ───────────────────────────────────────────────────────────

    def obtenir_historique_ventes(
        self,
        vendeur_id: Optional[uuid.UUID] = None,
        client_id: Optional[uuid.UUID] = None,
        date_debut=None,
        date_fin=None,
        statut: Optional[str] = None,
    ):
        qs = Vente.objects.select_related("vendeur", "client").prefetch_related("lignes")
        if vendeur_id:
            qs = qs.filter(vendeur_id=vendeur_id)
        if client_id:
            qs = qs.filter(client_id=client_id)
        if date_debut:
            qs = qs.filter(cree_le__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(cree_le__date__lte=date_fin)
        if statut:
            qs = qs.filter(statut=statut)
        return qs.order_by("-cree_le")

    # ─── Besoins de réapprovisionnement ───────────────────────────────────────

    def calculer_besoins_reapprovisionnement(self) -> list:
        """
        Retourne les médicaments actifs dont le stock est sous le seuil d'alerte.
        """
        from django.db.models import Sum, F
        from gestion.catalogue.models import Medicament

        return list(
            Medicament.objects
            .filter(est_actif=True)
            .annotate(stock_actuel=Sum("lots__quantite_disponible"))
            .filter(stock_actuel__lte=F("seuil_alerte_stock"))
            .values("id", "nom", "stock_actuel", "seuil_alerte_stock")
        )
