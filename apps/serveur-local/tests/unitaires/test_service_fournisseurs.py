"""
Tests unitaires du service fournisseurs (création BC + réception).

Les tests s'appuient sur les factories existantes du projet (usine_*).
Les tests d'intégration API vivent dans tests/integration/.
"""

from decimal import Decimal

import pytest


pytestmark = pytest.mark.django_db


def _dummy_user(django_user_model):
    return django_user_model.objects.create_user(
        username="acheteur", password="motdepasse123", email="a@x.bf",
    )


def test_creer_bon_commande_calcule_les_totaux(django_user_model):
    from gestion.fournisseurs.services import (
        LigneBCEntree, ServiceFournisseurs,
    )
    from gestion.fournisseurs.models import Fournisseur, StatutBonCommande

    user = _dummy_user(django_user_model)
    fournisseur = Fournisseur.objects.create(
        code="F001", nom="Grossiste BF", actif=True,
    )
    # medicament : on s'appuie sur l'usine si disponible, sinon skip
    try:
        from tests.usine.usine_medicaments import UsineMedicament
        med = UsineMedicament()
    except Exception:  # pragma: no cover
        pytest.skip("Usine medicaments indisponible dans ce contexte")

    bc = ServiceFournisseurs.creer_bon_commande(
        utilisateur=user,
        fournisseur_id=fournisseur.id,
        lignes=[
            LigneBCEntree(
                medicament_id=med.id, quantite=10,
                prix_unitaire_ht=Decimal("100.00"), taux_tva=Decimal("18.00"),
            ),
        ],
    )
    assert bc.statut == StatutBonCommande.BROUILLON
    assert bc.total_ht == Decimal("1000.00")
    assert bc.total_tva == Decimal("180.00")
    assert bc.total_ttc == Decimal("1180.00")
    assert bc.numero.startswith("BC-")


def test_reception_partielle_puis_totale_met_a_jour_statut(django_user_model):
    from datetime import date
    from gestion.fournisseurs.services import (
        LigneBCEntree, LigneReceptionEntree, ServiceFournisseurs,
    )
    from gestion.fournisseurs.models import Fournisseur, StatutBonCommande

    user = _dummy_user(django_user_model)
    fournisseur = Fournisseur.objects.create(code="F002", nom="Labo X", actif=True)
    try:
        from tests.usine.usine_medicaments import UsineMedicament
        med = UsineMedicament()
    except Exception:  # pragma: no cover
        pytest.skip("Usine medicaments indisponible")

    bc = ServiceFournisseurs.creer_bon_commande(
        utilisateur=user, fournisseur_id=fournisseur.id,
        lignes=[LigneBCEntree(medicament_id=med.id, quantite=10, prix_unitaire_ht=Decimal("50"))],
    )
    ServiceFournisseurs.envoyer_bon_commande(utilisateur=user, bon_commande_id=bc.id)
    ligne_bc = bc.lignes.first()

    ServiceFournisseurs.receptionner(
        utilisateur=user, bon_commande_id=bc.id,
        lignes=[LigneReceptionEntree(
            ligne_bc_id=ligne_bc.id, quantite_recue=4,
            numero_lot="LOT-A", date_peremption=date(2027, 12, 31),
            prix_achat_unitaire=Decimal("50"),
        )],
    )
    bc.refresh_from_db()
    assert bc.statut == StatutBonCommande.PARTIEL

    ServiceFournisseurs.receptionner(
        utilisateur=user, bon_commande_id=bc.id,
        lignes=[LigneReceptionEntree(
            ligne_bc_id=ligne_bc.id, quantite_recue=6,
            numero_lot="LOT-A", date_peremption=date(2027, 12, 31),
            prix_achat_unitaire=Decimal("50"),
        )],
    )
    bc.refresh_from_db()
    assert bc.statut == StatutBonCommande.RECU
    ligne_bc.refresh_from_db()
    assert ligne_bc.quantite_recue == 10


def test_sur_livraison_refusee(django_user_model):
    from datetime import date
    from gestion.fournisseurs.services import (
        LigneBCEntree, LigneReceptionEntree, ServiceFournisseurs,
        QuantiteReceptionInvalide,
    )
    from gestion.fournisseurs.models import Fournisseur

    user = _dummy_user(django_user_model)
    fournisseur = Fournisseur.objects.create(code="F003", nom="Grossiste Y", actif=True)
    try:
        from tests.usine.usine_medicaments import UsineMedicament
        med = UsineMedicament()
    except Exception:  # pragma: no cover
        pytest.skip("Usine medicaments indisponible")
    bc = ServiceFournisseurs.creer_bon_commande(
        utilisateur=user, fournisseur_id=fournisseur.id,
        lignes=[LigneBCEntree(medicament_id=med.id, quantite=5, prix_unitaire_ht=Decimal("10"))],
    )
    ServiceFournisseurs.envoyer_bon_commande(utilisateur=user, bon_commande_id=bc.id)
    ligne_bc = bc.lignes.first()
    with pytest.raises(QuantiteReceptionInvalide):
        ServiceFournisseurs.receptionner(
            utilisateur=user, bon_commande_id=bc.id,
            lignes=[LigneReceptionEntree(
                ligne_bc_id=ligne_bc.id, quantite_recue=6,
                numero_lot="LOT", date_peremption=date(2027, 1, 1),
                prix_achat_unitaire=Decimal("10"),
            )],
        )
