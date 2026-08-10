"""
Module : infrastructure/repositories/catalogue.py
Description : Repository pour les médicaments et lots du catalogue.
"""

import uuid
from typing import Optional

from .base import DepotAbstrait


class DepotMedicament(DepotAbstrait):
    """
    Repository pour les médicaments du catalogue.

    Fonctionnalités :
    - Recherche par nom, DCI, code CIS/ACL
    - Filtres par catégorie, statut, besoin d'ordonnance
    - Stocks disponibles agrégés
    - Alertes de stock
    """

    def trouver_par_id(self, id: uuid.UUID):
        """Retourne un Medicament actif avec ses relations ou None."""
        from gestion.catalogue.modeles import Medicament
        return (
            Medicament.objects
            .select_related("categorie")
            .prefetch_related("lots")
            .filter(id=id, est_actif=True)
            .first()
        )

    def trouver_par_code_cis(self, code_cis: str):
        """Retourne un Medicament par code CIS ou None."""
        from gestion.catalogue.modeles import Medicament
        return Medicament.objects.filter(code_cis=code_cis, est_actif=True).first()

    def sauvegarder(self, entite) -> object:
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        """Désactive un médicament (soft delete)."""
        from gestion.catalogue.modeles import Medicament
        updated = Medicament.objects.filter(id=id).update(est_actif=False)
        return updated > 0

    def lister(
        self,
        recherche: Optional[str] = None,
        categorie_id: Optional[uuid.UUID] = None,
        necessite_ordonnance: Optional[bool] = None,
        est_produit_controle: Optional[bool] = None,
        en_alerte_stock: bool = False,
    ) -> list:
        """Retourne la liste des médicaments actifs avec filtres."""
        from django.db.models import Q
        from gestion.catalogue.modeles import Medicament

        qs = Medicament.objects.filter(est_actif=True).select_related("categorie")
        if recherche:
            qs = qs.filter(
                Q(nom__icontains=recherche)
                | Q(denomination_commune_internationale__icontains=recherche)
                | Q(code_cis__icontains=recherche)
                | Q(fabricant__icontains=recherche)
            )
        if categorie_id:
            qs = qs.filter(categorie_id=categorie_id)
        if necessite_ordonnance is not None:
            qs = qs.filter(necessite_ordonnance=necessite_ordonnance)
        if est_produit_controle is not None:
            qs = qs.filter(est_produit_controle=est_produit_controle)
        return list(qs.order_by("nom"))

    def medicaments_en_alerte(self) -> list:
        """Retourne les médicaments dont le stock est en dessous du seuil d'alerte."""
        from gestion.catalogue.modeles import Medicament
        return [m for m in Medicament.objects.filter(est_actif=True) if m.est_en_alerte_stock]


class DepotLot(DepotAbstrait):
    """
    Repository pour les lots de médicaments.

    Un lot représente une livraison spécifique d'un médicament
    avec un numéro de lot fabricant, une date de péremption et un prix d'achat.
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

    def trouver_pour_update(self, id: uuid.UUID):
        """Retourne un Lot avec verrou SELECT FOR UPDATE."""
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
        disponibles_seulement: bool = False,
        non_perimes_seulement: bool = True,
    ) -> list:
        """Retourne les lots avec filtres, triés par date de péremption (FEFO)."""
        from gestion.catalogue.modeles import Lot
        from django.utils import timezone

        qs = Lot.objects.select_related("medicament").filter(est_actif=est_actif)
        if medicament_id:
            qs = qs.filter(medicament_id=medicament_id)
        if disponibles_seulement:
            qs = qs.filter(quantite_disponible__gt=0)
        if non_perimes_seulement:
            qs = qs.filter(date_peremption__gt=timezone.now().date())
        return list(qs.order_by("date_peremption"))

    def lots_perimant_bientot(self, jours: int = 90) -> list:
        """Retourne les lots qui périment dans les N prochains jours."""
        from gestion.catalogue.modeles import Lot
        from django.utils import timezone
        import datetime

        date_limite = timezone.now().date() + datetime.timedelta(days=jours)
        return list(
            Lot.objects
            .select_related("medicament")
            .filter(
                est_actif=True,
                quantite_disponible__gt=0,
                date_peremption__lte=date_limite,
                date_peremption__gt=timezone.now().date(),
            )
            .order_by("date_peremption")
        )
