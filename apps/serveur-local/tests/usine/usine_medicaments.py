"""
tests/usine/usine_medicaments.py
Usines factory_boy pour le catalogue de médicaments.
"""

import datetime
import uuid

import factory
from decimal import Decimal
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("fr_FR")


class UsineCategorie(DjangoModelFactory):
    class Meta:
        model = "catalogue.CategorieProduit"

    nom = factory.Sequence(lambda n: f"Catégorie {n}")
    code = factory.Sequence(lambda n: f"CAT{n:03d}")
    description = ""


class UsineMedicament(DjangoModelFactory):
    class Meta:
        model = "catalogue.Medicament"

    nom = factory.Sequence(lambda n: f"Amoxicilline {n}mg")
    denomination_commune_internationale = "Amoxicilline"
    categorie = factory.SubFactory(UsineCategorie)
    forme_pharmaceutique = "gelule"
    dosage = "500mg"
    fabricant = "PHARMA BF"
    code_cis = factory.Sequence(lambda n: f"CIS{n:08d}")
    prix_public = Decimal("800.00")
    prix_min_autorise = Decimal("700.00")
    prix_max_autorise = Decimal("900.00")
    necessite_ordonnance = False
    est_produit_controle = False
    seuil_alerte_stock = 20
    est_actif = True


class UsineMedicamentOrdonnance(UsineMedicament):
    necessite_ordonnance = True
    est_produit_controle = False
    nom = factory.Sequence(lambda n: f"Tramadol {n}mg")
    denomination_commune_internationale = "Tramadol"
    prix_public = Decimal("1200.00")


class UsineMedicamentControle(UsineMedicament):
    necessite_ordonnance = True
    est_produit_controle = True
    nom = factory.Sequence(lambda n: f"Morphine {n}mg")
    denomination_commune_internationale = "Morphine"
    prix_public = Decimal("2000.00")


class UsineLot(DjangoModelFactory):
    class Meta:
        model = "catalogue.Lot"

    medicament = factory.SubFactory(UsineMedicament)
    numero_lot = factory.Sequence(lambda n: f"LOT-2024-{n:04d}")
    quantite_initiale = 200
    quantite_disponible = 150
    prix_achat_unitaire = Decimal("500.00")
    date_peremption = factory.LazyFunction(
        lambda: datetime.date.today() + datetime.timedelta(days=365)
    )
    emplacement_stockage = "Rayon A1"
    est_actif = True


class UsineLotPerimantBientot(UsineLot):
    date_peremption = factory.LazyFunction(
        lambda: datetime.date.today() + datetime.timedelta(days=30)
    )


class UsineLotPerime(UsineLot):
    date_peremption = factory.LazyFunction(
        lambda: datetime.date.today() - datetime.timedelta(days=1)
    )
    quantite_disponible = 0
    est_actif = False
