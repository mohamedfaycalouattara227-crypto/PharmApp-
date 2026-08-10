"""
Module : infrastructure/repositories/ventes.py
Description : Repository pour les ventes et clôtures de caisse.

Ce repository isole complètement l'accès à la base de données
pour les entités Vente et ClotureCaisse.
Les services métier ne connaissent que cette interface — jamais l'ORM.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from .base import DepotAbstrait


class DepotVente(DepotAbstrait):
    """
    Repository pour les ventes PharmApp.

    Méthodes disponibles :
    - trouver_par_id, trouver_par_numero
    - sauvegarder, annuler
    - lister (avec filtres date, vendeur, client, statut)
    - compter_par_mode_paiement, total_journalier
    """

    def trouver_par_id(self, id: uuid.UUID):
        """Retourne une Vente avec ses relations ou None."""
        from gestion.ventes.models import Vente
        return (
            Vente.objects
            .select_related("vendeur", "client")
            .prefetch_related("lignes")
            .filter(id=id)
            .first()
        )

    def trouver_par_numero(self, numero: str):
        """Retourne une Vente par son numéro ou None."""
        from gestion.ventes.models import Vente
        return Vente.objects.filter(numero=numero).first()

    def sauvegarder(self, entite) -> object:
        """Sauvegarde (create ou update) une Vente."""
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        """Les ventes ne sont jamais supprimées — annulation uniquement."""
        raise NotImplementedError(
            "Les ventes ne peuvent pas être supprimées. Utilisez annuler()."
        )

    def annuler(self, id: uuid.UUID, motif: str, utilisateur) -> bool:
        """
        Annule logiquement une vente (statut → 'annulee').

        Returns:
            True si l'annulation a réussi, False si la vente est introuvable.
        """
        from gestion.ventes.modeles import Vente
        vente = Vente.objects.filter(id=id).first()
        if not vente:
            return False
        vente.statut = "annulee"
        vente.motif_annulation = motif
        vente.annulee_par = utilisateur
        from django.utils import timezone
        vente.annulee_le = timezone.now()
        vente.save(update_fields=["statut", "motif_annulation", "annulee_par", "annulee_le"])
        return True

    def lister(
        self,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        vendeur_id: Optional[uuid.UUID] = None,
        client_id: Optional[uuid.UUID] = None,
        statut: Optional[str] = None,
        mode_paiement: Optional[str] = None,
    ) -> list:
        """Retourne une liste filtrée de ventes triées par date décroissante."""
        from gestion.ventes.modeles import Vente
        qs = (
            Vente.objects
            .select_related("vendeur", "client")
            .prefetch_related("lignes")
        )
        if date_debut:
            qs = qs.filter(cree_le__date__gte=date_debut)
        if date_fin:
            qs = qs.filter(cree_le__date__lte=date_fin)
        if vendeur_id:
            qs = qs.filter(vendeur_id=vendeur_id)
        if client_id:
            qs = qs.filter(client_id=client_id)
        if statut:
            qs = qs.filter(statut=statut)
        if mode_paiement:
            qs = qs.filter(mode_paiement=mode_paiement)
        return list(qs.order_by("-cree_le"))

    def total_journalier(self, date_cloture: date) -> Decimal:
        """
        Calcule le chiffre d'affaires total d'une journée (ventes validées uniquement).

        Args:
            date_cloture: Date pour laquelle calculer le total.

        Returns:
            Montant total en FCFA (Decimal).
        """
        from decimal import Decimal
        from django.db.models import Sum
        from gestion.ventes.modeles import Vente

        resultat = Vente.objects.filter(
            cree_le__date=date_cloture,
            statut="validee",
        ).aggregate(total=Sum("montant_total"))

        return resultat["total"] or Decimal("0.00")

    def compter_par_mode_paiement(self, date_cloture: date) -> dict:
        """
        Retourne le total par mode de paiement pour une journée.

        Returns:
            {"especes": Decimal, "mobile_money": Decimal, …}
        """
        from decimal import Decimal
        from django.db.models import Sum
        from gestion.ventes.modeles import Vente

        resultats = (
            Vente.objects
            .filter(cree_le__date=date_cloture, statut="validee")
            .values("mode_paiement")
            .annotate(total=Sum("montant_total"))
        )
        return {r["mode_paiement"]: r["total"] or Decimal("0.00") for r in resultats}

    def nombre_ventes_journalier(self, date_cloture: date) -> int:
        """Retourne le nombre de ventes validées pour une journée."""
        from gestion.ventes.modeles import Vente
        return Vente.objects.filter(
            cree_le__date=date_cloture,
            statut="validee",
        ).count()


class DepotClotureCaisse(DepotAbstrait):
    """Repository pour les clôtures de caisse journalières."""

    def trouver_par_id(self, id: uuid.UUID):
        from gestion.ventes.modeles import ClotureCaisse
        return ClotureCaisse.objects.select_related("effectuee_par").filter(id=id).first()

    def trouver_par_date(self, date_cloture: date):
        """Retourne la clôture pour une date donnée ou None."""
        from gestion.ventes.modeles import ClotureCaisse
        return ClotureCaisse.objects.filter(date_cloture=date_cloture).first()

    def sauvegarder(self, entite) -> object:
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        raise NotImplementedError("Les clôtures de caisse sont immuables.")

    def lister(self, annee: Optional[int] = None, mois: Optional[int] = None) -> list:
        from gestion.ventes.modeles import ClotureCaisse
        qs = ClotureCaisse.objects.select_related("effectuee_par").order_by("-date_cloture")
        if annee:
            qs = qs.filter(date_cloture__year=annee)
        if mois:
            qs = qs.filter(date_cloture__month=mois)
        return list(qs)
