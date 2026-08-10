"""
tests/usine/usine_stocks.py
Usine factory_boy pour les stocks, inventaires et alertes.
"""

import factory
from factory.django import DjangoModelFactory

from .usine_medicaments import UsineLot, UsineMedicament
from .usine_utilisateurs import UsineGestionnaireStock


class UsineAlerte(DjangoModelFactory):
    class Meta:
        model = "stocks.AlerteStock"

    medicament = factory.SubFactory(UsineMedicament)
    niveau = "alerte"
    est_resolue = False
    stock_au_moment_alerte = 5
    seuil_depasse = 20


class UsineInventaire(DjangoModelFactory):
    class Meta:
        model = "stocks.Inventaire"

    reference = factory.Sequence(lambda n: f"INV-2024-{n:04d}")
    statut = "en_cours"
    demarre_par = factory.SubFactory(UsineGestionnaireStock)


class UsineMouvementStock(DjangoModelFactory):
    class Meta:
        model = "stocks.MouvementStock"

    lot = factory.SubFactory(UsineLot)
    type_mouvement = "vente"
    quantite = -3  # Sortie vente
    quantite_avant = 150
    quantite_apres = 147
    reference_document = factory.Sequence(lambda n: f"V-2024-{n:06d}")
    motif = ""
    effectue_par = factory.SubFactory(UsineGestionnaireStock)
