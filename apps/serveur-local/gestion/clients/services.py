"""
Module : gestion/clients/services.py
Description : Service métier pour la gestion des clients de PharmApp.
"""

import logging
import uuid

from django.db import transaction
from decimal import Decimal
from typing import Any, Optional

from gestion.exceptions import (
    PermissionRefusee,
    CreditNonAutorise,
    PlafondCreditDepasse,
    ClientIntrouvable,
    TelephoneDejaUtilise,
    ClientDejaExistant,
)

# Imports module-level pour que patch() fonctionne dans les tests
from gestion.clients.models import Client
from gestion.ventes.models import Vente

logger = logging.getLogger("pharmapp.clients")

# Rôle minimum pour créer/modifier un client
ROLE_MINIMUM_CLIENT = "caissier"


class ServiceClient:
    """Service métier pour la gestion des clients."""

    # ─── Création ─────────────────────────────────────────────────────────────

    def creer_client(
        self,
        prenom: str,
        nom: str,
        donnees: dict,
        utilisateur,
    ):
        """
        Crée un nouveau client.

        Raises:
            PermissionRefusee: Si l'utilisateur est stagiaire.
            TelephoneDejaUtilise: Si le numéro existe déjà.
        """
        if not utilisateur.a_permission_role(ROLE_MINIMUM_CLIENT):
            raise PermissionRefusee(
                f"La création de clients requiert au moins le rôle {ROLE_MINIMUM_CLIENT}."
            )

        telephone = donnees.get("telephone", "")
        if telephone and Client.objects.filter(telephone=telephone, est_actif=True).exists():
            raise TelephoneDejaUtilise(
                f"Le numéro {telephone} est déjà enregistré pour un autre client."
            )

        client = Client(
            prenom=prenom,
            nom=nom,
            telephone=telephone,
            email=donnees.get("email", ""),
            type_client=donnees.get("type_client", "particulier"),
            adresse=donnees.get("adresse", ""),
            notes=donnees.get("notes", ""),
            credit_autorise=donnees.get("credit_autorise", False),
            plafond_credit=Decimal(str(donnees.get("plafond_credit", "0.00"))),
        )
        client.save()

        logger.info("Client créé : %s %s (ID=%s)", prenom, nom, client.id)
        return client

    # ─── Modification ─────────────────────────────────────────────────────────

    def modifier_client(
        self,
        client_id: uuid.UUID,
        donnees: dict,
        utilisateur,
    ):
        """
        Modifie un client existant.

        Raises:
            PermissionRefusee: Si l'utilisateur est stagiaire.
            ValueError: Si le client n'existe pas.
        """
        if not utilisateur.a_permission_role(ROLE_MINIMUM_CLIENT):
            raise PermissionRefusee(
                f"La modification de clients requiert au moins le rôle {ROLE_MINIMUM_CLIENT}."
            )

        client = Client.objects.filter(id=client_id, est_actif=True).first()
        if client is None:
            raise ValueError(f"Client introuvable (ID={client_id}).")

        champs_autorites = {
            "prenom", "nom", "telephone", "email", "adresse",
            "type_client", "assureur", "numero_assurance",
            "taux_prise_en_charge", "credit_autorise", "plafond_credit", "notes",
            # Étape 5 : allergies — la restriction d'accès est gérée dans la vue (partial_update)
            "allergies",
        }
        for champ, valeur in donnees.items():
            if champ in champs_autorites:
                setattr(client, champ, valeur)

        client.save()
        return client

    # ─── Crédit ───────────────────────────────────────────────────────────────

    def verifier_credit_disponible(
        self,
        client,
        montant_commande: Decimal,
    ) -> None:
        """
        Vérifie si un client peut payer en crédit.

        Raises:
            CreditNonAutorise: Si le client n'a pas de crédit autorisé.
            PlafondCreditDepasse: Si le montant dépasse le plafond disponible.
        """
        if not getattr(client, "credit_autorise", False):
            raise CreditNonAutorise(
                "Ce client n'est pas autorisé à utiliser le crédit."
            )

        solde = self._calculer_solde_credit(client.id)
        if montant_commande > solde["disponible"]:
            raise PlafondCreditDepasse(
                f"Plafond de crédit dépassé. Disponible : {solde['disponible']} FCFA, "
                f"demandé : {montant_commande} FCFA.",
            )

    def _calculer_solde_credit(self, client_id: uuid.UUID) -> dict:
        """
        Calcule le solde de crédit courant d'un client.

        Returns:
            {"plafond": Decimal, "utilise": Decimal, "disponible": Decimal}
        """
        from django.db.models import Sum

        client = Client.objects.filter(id=client_id).first()
        if not client:
            return {
                "plafond": Decimal("0"),
                "utilise": Decimal("0"),
                "disponible": Decimal("0"),
            }

        total_credit = (
            Vente.objects
            .filter(client_id=client_id, mode_paiement="credit", statut="validee")
            .aggregate(total=Sum("montant_total"))["total"]
            or Decimal("0")
        )

        plafond = client.plafond_credit
        disponible = max(Decimal("0"), plafond - total_credit)

        return {
            "plafond": plafond,
            "utilise": total_credit,
            "disponible": disponible,
        }

    # ─── RGPD ─────────────────────────────────────────────────────────────────

    def anonymiser_client(self, client_id: uuid.UUID, utilisateur) -> None:
        """Anonymise un client (droit à l'oubli — RGPD)."""
        if not utilisateur.a_permission_role("pharmacien_adjoint"):
            raise PermissionRefusee(
                "L'anonymisation RGPD requiert au moins le rôle pharmacien_adjoint."
            )

        with transaction.atomic():
            client = (
                Client.objects.filter(id=client_id).select_for_update().first()
            )
            if not client:
                raise ValueError(f"Client introuvable (ID={client_id}).")

            client.anonymiser()
        logger.info("Client anonymisé (RGPD) : ID=%s", client_id)
