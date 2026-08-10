"""
tests/usine/usine_clients.py
Usine factory_boy pour les clients de la pharmacie.
"""

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("fr_FR")


class UsineClient(DjangoModelFactory):
    class Meta:
        model = "clients.Client"

    prenom = factory.LazyFunction(fake.first_name)
    nom = factory.LazyFunction(fake.last_name)
    telephone = factory.Sequence(lambda n: f"+226 70 {n:02d} {(n*7)%100:02d} {(n*13)%100:02d}")
    type_client = "particulier"
    est_actif = True
    est_anonymise = False
    credit_autorise = False
    plafond_credit = Decimal("0.00")


class UsineClientAssurance(UsineClient):
    type_client = "assurance"
    organisme_assurance = "CARFO"
    numero_assurance = factory.Sequence(lambda n: f"ASS-BF-{n:06d}")
    credit_autorise = True
    plafond_credit = Decimal("50000.00")


class UsineClientCredit(UsineClient):
    """Client particulier avec crédit autorisé (alias pratique pour les tests de plafond)."""
    credit_autorise = True
    plafond_credit = Decimal("50000.00")
