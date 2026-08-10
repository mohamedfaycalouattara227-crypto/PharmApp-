"""
tests/usine/usine_ventes.py
Usine factory_boy pour les ventes et lignes de vente.
"""

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from .usine_medicaments import UsineLot
from .usine_clients import UsineClient
from .usine_utilisateurs import UsineCaissier


class UsineVente(DjangoModelFactory):
    class Meta:
        model = "ventes.Vente"

    class Params:
        # Alias de fixture : le modèle métier nomme ce champ « vendeur ».
        caissier = None

    numero = factory.Sequence(lambda n: f"V-2024-{n:06d}")
    vendeur = factory.Maybe(
        "caissier",
        yes_declaration=factory.SelfAttribute("caissier"),
        no_declaration=factory.SubFactory(UsineCaissier),
    )
    client = factory.SubFactory(UsineClient)
    mode_paiement = "especes"
    montant_total = Decimal("2400.00")
    montant_encaisse = Decimal("2500.00")
    montant_rendu = Decimal("100.00")
    statut = "validee"


class UsineVenteAnnulee(UsineVente):
    statut = "annulee"
    motif_annulation = "Erreur de saisie"


class UsineLigneVente(DjangoModelFactory):
    class Meta:
        model = "ventes.LigneVente"

    vente = factory.SubFactory(UsineVente)
    lot = factory.SubFactory(UsineLot)
    # Le médicament de la ligne est celui du lot : toute divergence rendrait
    # la ligne incohérente avec le mouvement de stock associé.
    medicament = factory.LazyAttribute(lambda o: o.lot.medicament)
    quantite = 3
    prix_unitaire = Decimal("800.00")
    taux_remise = Decimal("0.00")
