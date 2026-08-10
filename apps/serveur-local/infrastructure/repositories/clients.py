"""
Module : infrastructure/repositories/clients.py
Description : Repository pour les clients et leur historique d'achats.
"""

import uuid
from typing import Optional

from .base import DepotAbstrait


class DepotClient(DepotAbstrait):
    """
    Repository pour les clients de la pharmacie.

    Fonctionnalités :
    - CRUD client (soft delete uniquement)
    - Recherche multi-critères (nom, téléphone, numéro d'assurance)
    - Historique des achats
    - Gestion du crédit
    """

    def trouver_par_id(self, id: uuid.UUID):
        """Retourne un Client actif ou None."""
        from gestion.clients.modeles import Client
        return (
            Client.objects
            .filter(id=id, est_actif=True)
            .first()
        )

    def trouver_par_telephone(self, telephone: str):
        """Retourne un Client par numéro de téléphone ou None."""
        from gestion.clients.modeles import Client
        return Client.objects.filter(
            telephone=telephone, est_actif=True
        ).first()

    def trouver_par_numero_assurance(self, numero: str):
        """Retourne un Client par numéro d'assurance ou None."""
        from gestion.clients.modeles import Client
        return Client.objects.filter(
            numero_assurance=numero, est_actif=True
        ).first()

    def sauvegarder(self, entite) -> object:
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        """Désactive un client (soft delete — RGPD)."""
        from gestion.clients.modeles import Client
        updated = Client.objects.filter(id=id).update(est_actif=False)
        return updated > 0

    def lister(
        self,
        recherche: Optional[str] = None,
        type_client: Optional[str] = None,
        credit_autorise: Optional[bool] = None,
        inclure_anonymises: bool = False,
    ) -> list:
        """
        Retourne la liste des clients actifs avec filtres optionnels.

        Args:
            recherche: Terme de recherche (nom, prénom, téléphone).
            type_client: Filtre par type de client.
            credit_autorise: Filtre par autorisation de crédit.
            inclure_anonymises: Si True, inclut les clients anonymisés.
        """
        from django.db.models import Q
        from gestion.clients.modeles import Client

        qs = Client.objects.filter(est_actif=True)
        if not inclure_anonymises:
            qs = qs.filter(est_anonymise=False)
        if recherche:
            qs = qs.filter(
                Q(nom__icontains=recherche)
                | Q(prenom__icontains=recherche)
                | Q(telephone__icontains=recherche)
                | Q(numero_assurance__icontains=recherche)
            )
        if type_client:
            qs = qs.filter(type_client=type_client)
        if credit_autorise is not None:
            qs = qs.filter(credit_autorise=credit_autorise)
        return list(qs.order_by("nom", "prenom"))

    def historique_achats(self, client_id: uuid.UUID) -> list:
        """Retourne l'historique des ventes pour un client."""
        from gestion.ventes.modeles import Vente
        return list(
            Vente.objects
            .filter(client_id=client_id)
            .select_related("vendeur")
            .prefetch_related("lignes__lot__medicament")
            .order_by("-cree_le")
        )

    def solde_credit(self, client_id: uuid.UUID) -> dict:
        """
        Calcule le solde de crédit courant d'un client.

        Returns:
            {"plafond": Decimal, "utilise": Decimal, "disponible": Decimal}
        """
        from decimal import Decimal
        from django.db.models import Sum
        from gestion.ventes.modeles import Vente

        client = self.trouver_par_id(client_id)
        if not client:
            return {"plafond": Decimal("0"), "utilise": Decimal("0"), "disponible": Decimal("0")}

        utilise = Vente.objects.filter(
            client_id=client_id,
            mode_paiement="credit",
            statut="validee",
        ).aggregate(total=Sum("montant_total"))["total"] or Decimal("0")

        plafond = client.plafond_credit or Decimal("0")
        return {
            "plafond": plafond,
            "utilise": utilise,
            "disponible": max(Decimal("0"), plafond - utilise),
        }
