"""
tests/usine/usine_utilisateurs.py
Usine factory_boy pour les utilisateurs PharmApp.
"""

import factory
from gestion.authentification.models import UtilisateurPharmacien
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("fr_FR")


class UsineUtilisateurPharmacien(DjangoModelFactory):
    """Usine pour créer des utilisateurs pharmaciens en base de test."""

    class Meta:
        model = UtilisateurPharmacien

    prenom = factory.LazyFunction(fake.first_name)
    nom = factory.LazyFunction(fake.last_name)
    email = factory.LazyAttribute(
        lambda obj: f"{obj.prenom.lower()}.{obj.nom.lower()}@pharmapp-test.bf"
    )
    numero_ordre = factory.Sequence(lambda n: f"ORD-{n:04d}")
    role = "caissier"
    est_actif = True

    @factory.post_generation
    def mot_de_passe(obj, create, extracted, **kwargs):
        mot = extracted or "motDePasse@Securise1!"
        obj.set_password(mot)
        if create:
            obj.save(update_fields=["password"])


class UsineCaissier(UsineUtilisateurPharmacien):
    role = "caissier"


class UsineAssistant(UsineUtilisateurPharmacien):
    role = "assistant"


class UsineGestionnaireStock(UsineUtilisateurPharmacien):
    role = "gestionnaire_stock"


class UsinePharmacienAdjoint(UsineUtilisateurPharmacien):
    role = "pharmacien_adjoint"
    numero_ordre = factory.Sequence(lambda n: f"BF-PHARMA-{n:04d}")


class UsineTitulaire(UsineUtilisateurPharmacien):
    role = "titulaire"
    numero_ordre = factory.Sequence(lambda n: f"BF-TITRE-{n:04d}")
