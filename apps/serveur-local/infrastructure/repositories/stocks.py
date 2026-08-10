"""
Module : infrastructure/repositories/stocks.py
Description : Repository pour les stocks, inventaires et alertes.
"""

import uuid
from decimal import Decimal
from typing import Optional

from .base import DepotAbstrait


class DepotStock(DepotAbstrait):
    """
    Repository pour les lots de stock et mouvements associés.

    Couvre :
    - Lots (Lot) et leurs mouvements (MouvementStock)
    - Inventaires (Inventaire, LigneInventaire)
    - Alertes de stock (AlerteStock)
    - Seuils de réapprovisionnement (SeuilReapprovisionnement)
    """

    def trouver_par_id(self, id: uuid.UUID):
        """Retourne un Lot avec ses relations ou None."""
        from gestion.catalogue.modeles import Lot
        return (
            Lot.objects
            .select_related("medicament")
            .filter(id=id)
            .first()
        )

    def trouver_lot_pour_update(self, id: uuid.UUID):
        """Retourne un Lot avec verrou SELECT FOR UPDATE (dans une transaction)."""
        from gestion.catalogue.modeles import Lot
        return Lot.objects.select_for_update().filter(id=id).first()

    def sauvegarder(self, entite) -> object:
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        """Désactive un lot (soft delete)."""
        from gestion.catalogue.modeles import Lot
        updated = Lot.objects.filter(id=id).update(est_actif=False)
        return updated > 0

    def lister(
        self,
        medicament_id: Optional[uuid.UUID] = None,
        est_actif: bool = True,
        en_alerte: bool = False,
    ) -> list:
        """Retourne les lots correspondant aux filtres, triés FEFO."""
        from gestion.catalogue.modeles import Lot
        from django.utils import timezone

        qs = Lot.objects.select_related("medicament").filter(est_actif=est_actif)
        if medicament_id:
            qs = qs.filter(medicament_id=medicament_id)
        if en_alerte:
            qs = qs.filter(quantite_disponible__lte=models.F("medicament__seuil_alerte_stock"))
        return list(qs.order_by("date_peremption"))

    def lots_fefo(self, medicament_id: uuid.UUID) -> list:
        """
        Retourne les lots disponibles pour un médicament, triés FEFO
        (First Expired, First Out) — les plus proches péremption en premier.

        Args:
            medicament_id: UUID du médicament.

        Returns:
            Liste de lots actifs, non périmés, quantité > 0, triés par date_peremption.
        """
        from gestion.catalogue.modeles import Lot
        from django.utils import timezone

        return list(
            Lot.objects
            .filter(
                medicament_id=medicament_id,
                est_actif=True,
                quantite_disponible__gt=0,
                date_peremption__gt=timezone.now().date(),
            )
            .order_by("date_peremption")
        )

    def creer_mouvement(
        self,
        lot,
        type_mouvement: str,
        quantite: int,
        quantite_avant: int,
        quantite_apres: int,
        reference_document: str = "",
        motif: str = "",
        effectue_par=None,
    ):
        """Crée un mouvement de stock dans le journal."""
        from gestion.catalogue.modeles import MouvementStock
        return MouvementStock.objects.create(
            lot=lot,
            type_mouvement=type_mouvement,
            quantite=quantite,
            quantite_avant=quantite_avant,
            quantite_apres=quantite_apres,
            reference_document=reference_document,
            motif=motif,
            effectue_par=effectue_par,
        )

    def alertes_actives(self) -> list:
        """Retourne toutes les alertes de stock actives."""
        from gestion.stocks.modeles import AlerteStock
        return list(
            AlerteStock.objects
            .select_related("medicament", "lot", "acquittee_par")
            .filter(statut="active")
            .order_by("-cree_le")
        )

    def creer_alerte(
        self,
        type_alerte: str,
        medicament,
        lot=None,
        message: str = "",
        valeur_actuelle: int = 0,
        seuil_alerte: int = 0,
        date_peremption_concernee=None,
    ):
        """Crée ou récupère une alerte de stock pour un médicament."""
        from gestion.stocks.modeles import AlerteStock
        alerte, cree = AlerteStock.objects.get_or_create(
            medicament=medicament,
            type_alerte=type_alerte,
            statut="active",
            defaults={
                "lot": lot,
                "message": message,
                "valeur_actuelle": valeur_actuelle,
                "seuil_alerte": seuil_alerte,
                "date_peremption_concernee": date_peremption_concernee,
            },
        )
        return alerte, cree
