"""
tests/integration/test_api_fournisseurs_complet.py
Tests d'intégration exhaustifs de l'API Fournisseurs / Bons de commande.

Branches couvertes :
  - GET  /api/fournisseurs/           : filtres actif, q (recherche)
  - POST /api/fournisseurs/           : création, permissions gestionnaire requis
  - PATCH /api/fournisseurs/<id>/     : modification partielle
  - DELETE /api/fournisseurs/<id>/    : suppression
  - GET  /api/bons-commande/          : liste, filtres statut/fournisseur
  - POST /api/bons-commande/          : création avec lignes
  - POST /api/bons-commande/<id>/envoyer/    : transition brouillon→envoyé
  - POST /api/bons-commande/<id>/annuler/    : avec motif
  - POST /api/bons-commande/<id>/receptionner/ : réception partielle et totale
  - Contrôle accès : caissier bloqué (403), gestionnaire/titulaire autorisés
"""

import uuid
import pytest
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APIClient

from tests.usine.usine_utilisateurs import (
    UsineGestionnaireStock,
    UsineCaissier,
    UsineTitulaire,
    UsinePharmacienAdjoint,
)
from tests.usine.usine_medicaments import UsineMedicament, UsineCategorie

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def gestionnaire(db):
    return UsineGestionnaireStock.create()


@pytest.fixture
def caissier(db):
    return UsineCaissier.create()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create()


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


@pytest.fixture
def api_gestionnaire(client_api, gestionnaire):
    client_api.force_authenticate(user=gestionnaire)
    return client_api


@pytest.fixture
def api_caissier(client_api, caissier):
    client_api.force_authenticate(user=caissier)
    return client_api


@pytest.fixture
def api_titulaire(client_api, titulaire):
    client_api.force_authenticate(user=titulaire)
    return client_api


@pytest.fixture
def api_adjoint(client_api, adjoint):
    client_api.force_authenticate(user=adjoint)
    return client_api


@pytest.fixture
def fournisseur(db):
    """Crée un fournisseur directement en base."""
    from gestion.fournisseurs.models import Fournisseur
    return Fournisseur.objects.create(
        code=f"FOUR-{str(uuid.uuid4())[:8].upper()}",
        nom="PharmDistrib SARL",
        telephone="70111222",
        email="contact@pharmdistrib.bf",
        ville="Ouagadougou",
        actif=True,
    )


@pytest.fixture
def fournisseur_inactif(db):
    """Fournisseur inactif pour tester le filtre actif=false."""
    from gestion.fournisseurs.models import Fournisseur
    return Fournisseur.objects.create(
        code=f"OLD-{str(uuid.uuid4())[:8].upper()}",
        nom="Ancien Distributeur",
        actif=False,
    )


@pytest.fixture
def medicament(db):
    cat = UsineCategorie.create(nom="Antibiotiques")
    return UsineMedicament.create(categorie=cat, prix_public=Decimal("1000"))


@pytest.fixture
def bon_commande_brouillon(db, fournisseur, gestionnaire, medicament):
    """Bon de commande au statut brouillon."""
    from gestion.fournisseurs.models import BonCommande, LigneBonCommande
    bc = BonCommande.objects.create(
        fournisseur=fournisseur,
        cree_par=gestionnaire,
        statut="brouillon",
    )
    LigneBonCommande.objects.create(
        bon_commande=bc,
        medicament=medicament,
        quantite_commandee=10,
        prix_unitaire_ht=Decimal("900.00"),
    )
    return bc


# ─── Tests Fournisseurs ───────────────────────────────────────────────────────


class TestListeFournisseurs:
    """GET /api/fournisseurs/"""

    def test_gestionnaire_peut_lister(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.get("/api/fournisseurs/")
        assert rep.status_code == status.HTTP_200_OK
        noms = [f["nom"] for f in rep.json()["results"]]
        assert "PharmDistrib SARL" in noms

    def test_caissier_bloque_403(self, api_caissier, fournisseur):
        rep = api_caissier.get("/api/fournisseurs/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_non_authentifie_401(self, client_api):
        rep = client_api.get("/api/fournisseurs/")
        assert rep.status_code == status.HTTP_401_UNAUTHORIZED

    def test_filtre_actif_vrai(self, api_gestionnaire, fournisseur, fournisseur_inactif):
        rep = api_gestionnaire.get("/api/fournisseurs/?actif=true")
        assert rep.status_code == status.HTTP_200_OK
        noms = [f["nom"] for f in rep.json()["results"]]
        assert "PharmDistrib SARL" in noms
        assert "Ancien Distributeur" not in noms

    def test_filtre_actif_faux(self, api_gestionnaire, fournisseur, fournisseur_inactif):
        rep = api_gestionnaire.get("/api/fournisseurs/?actif=false")
        assert rep.status_code == status.HTTP_200_OK
        noms = [f["nom"] for f in rep.json()["results"]]
        assert "Ancien Distributeur" in noms
        assert "PharmDistrib SARL" not in noms

    def test_recherche_par_nom(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.get("/api/fournisseurs/?q=PharmDist")
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] >= 1

    def test_recherche_sans_resultat(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.get("/api/fournisseurs/?q=xxxxINEXISTANT")
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] == 0

    def test_adjoint_peut_lister(self, api_adjoint, fournisseur):
        rep = api_adjoint.get("/api/fournisseurs/")
        assert rep.status_code == status.HTTP_200_OK

    def test_titulaire_peut_lister(self, api_titulaire, fournisseur):
        rep = api_titulaire.get("/api/fournisseurs/")
        assert rep.status_code == status.HTTP_200_OK


class TestCreerFournisseur:
    """POST /api/fournisseurs/"""

    def test_creation_valide(self, api_gestionnaire):
        payload = {
            "code": f"NEW-{str(uuid.uuid4())[:6].upper()}",
            "nom": "Nouveau Fournisseur SA",
            "telephone": "70000001",
            "email": "nouveau@fourn.bf",
            "ville": "Bobo-Dioulasso",
        }
        rep = api_gestionnaire.post("/api/fournisseurs/", data=payload, format="json")
        assert rep.status_code == status.HTTP_201_CREATED
        assert rep.json()["nom"] == "Nouveau Fournisseur SA"

    def test_creation_sans_code_retourne_400(self, api_gestionnaire):
        rep = api_gestionnaire.post(
            "/api/fournisseurs/",
            data={"nom": "Sans Code"},
            format="json",
        )
        assert rep.status_code == status.HTTP_400_BAD_REQUEST

    def test_caissier_bloque_403(self, api_caissier):
        rep = api_caissier.post(
            "/api/fournisseurs/",
            data={"code": "TEST01", "nom": "Interdit"},
            format="json",
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_code_duplique_retourne_400(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.post(
            "/api/fournisseurs/",
            data={"code": fournisseur.code, "nom": "Doublon"},
            format="json",
        )
        assert rep.status_code == status.HTTP_400_BAD_REQUEST


class TestModifierFournisseur:
    """PATCH /api/fournisseurs/<id>/"""

    def test_modification_partielle(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.patch(
            f"/api/fournisseurs/{fournisseur.id}/",
            data={"telephone": "70999888"},
            format="json",
        )
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["telephone"] == "70999888"

    def test_caissier_bloque_403(self, api_caissier, fournisseur):
        rep = api_caissier.patch(
            f"/api/fournisseurs/{fournisseur.id}/",
            data={"telephone": "00000000"},
            format="json",
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_fournisseur_inexistant_retourne_404(self, api_gestionnaire):
        rep = api_gestionnaire.patch(
            f"/api/fournisseurs/{uuid.uuid4()}/",
            data={"nom": "X"},
            format="json",
        )
        assert rep.status_code == status.HTTP_404_NOT_FOUND


class TestSupprimerFournisseur:
    """DELETE /api/fournisseurs/<id>/"""

    def test_suppression_reussie(self, api_titulaire, db):
        from gestion.fournisseurs.models import Fournisseur
        f = Fournisseur.objects.create(
            code=f"DEL-{str(uuid.uuid4())[:6].upper()}",
            nom="À Supprimer",
        )
        rep = api_titulaire.delete(f"/api/fournisseurs/{f.id}/")
        assert rep.status_code == status.HTTP_204_NO_CONTENT

    def test_caissier_bloque_403(self, api_caissier, fournisseur):
        rep = api_caissier.delete(f"/api/fournisseurs/{fournisseur.id}/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN


# ─── Tests Bons de commande ───────────────────────────────────────────────────


class TestListeBonsCommande:
    """GET /api/bons-commande/"""

    def test_gestionnaire_liste_bons(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.get("/api/bons-commande/")
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] >= 1

    def test_caissier_bloque_403(self, api_caissier):
        rep = api_caissier.get("/api/bons-commande/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_filtre_par_statut_brouillon(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.get("/api/bons-commande/?statut=brouillon")
        assert rep.status_code == status.HTTP_200_OK
        statuts = [bc["statut"] for bc in rep.json()["results"]]
        assert all(s == "brouillon" for s in statuts)

    def test_filtre_par_statut_recu_vide(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.get("/api/bons-commande/?statut=recu")
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] == 0

    def test_filtre_par_fournisseur(
        self, api_gestionnaire, bon_commande_brouillon, fournisseur
    ):
        rep = api_gestionnaire.get(
            f"/api/bons-commande/?fournisseur={fournisseur.id}"
        )
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] >= 1


class TestCreerBonCommande:
    """POST /api/bons-commande/"""

    def test_creation_valide(self, api_gestionnaire, fournisseur, medicament):
        payload = {
            "fournisseur_id": str(fournisseur.id),
            "lignes": [
                {
                    "medicament_id": str(medicament.id),
                    "quantite": 5,
                    "prix_unitaire_ht": "900.00",
                }
            ],
        }
        rep = api_gestionnaire.post(
            "/api/bons-commande/", data=payload, format="json"
        )
        assert rep.status_code == status.HTTP_201_CREATED
        assert rep.json()["statut"] == "brouillon"
        assert len(rep.json()["lignes"]) == 1

    def test_caissier_bloque_403(self, api_caissier, fournisseur, medicament):
        rep = api_caissier.post(
            "/api/bons-commande/",
            data={
                "fournisseur_id": str(fournisseur.id),
                "lignes": [
                    {
                        "medicament_id": str(medicament.id),
                        "quantite": 1,
                        "prix_unitaire_ht": "500.00",
                    }
                ],
            },
            format="json",
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_sans_lignes_retourne_400(self, api_gestionnaire, fournisseur):
        rep = api_gestionnaire.post(
            "/api/bons-commande/",
            data={"fournisseur_id": str(fournisseur.id), "lignes": []},
            format="json",
        )
        assert rep.status_code == status.HTTP_400_BAD_REQUEST

    def test_fournisseur_inexistant_retourne_400(
        self, api_gestionnaire, medicament
    ):
        rep = api_gestionnaire.post(
            "/api/bons-commande/",
            data={
                "fournisseur_id": str(uuid.uuid4()),
                "lignes": [
                    {
                        "medicament_id": str(medicament.id),
                        "quantite": 1,
                        "prix_unitaire_ht": "500.00",
                    }
                ],
            },
            format="json",
        )
        assert rep.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


class TestEnvoyerBonCommande:
    """POST /api/bons-commande/<id>/envoyer/"""

    def test_envoi_brouillon_devient_envoye(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/envoyer/"
        )
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["statut"] == "envoye"

    def test_envoi_deja_envoye_retourne_erreur(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        # Premier envoi
        api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/envoyer/"
        )
        # Second envoi → doit échouer
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/envoyer/"
        )
        assert rep.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_409_CONFLICT,
        )

    def test_caissier_bloque_403(
        self, api_caissier, bon_commande_brouillon
    ):
        rep = api_caissier.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/envoyer/"
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN


class TestAnnulerBonCommande:
    """POST /api/bons-commande/<id>/annuler/"""

    def test_annulation_avec_motif(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/annuler/",
            data={"motif": "Rupture fournisseur"},
            format="json",
        )
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["statut"] == "annule"

    def test_annulation_sans_motif_retourne_400(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/annuler/",
            data={},
            format="json",
        )
        assert rep.status_code == status.HTTP_400_BAD_REQUEST

    def test_caissier_bloque_403(
        self, api_caissier, bon_commande_brouillon
    ):
        rep = api_caissier.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/annuler/",
            data={"motif": "Test"},
            format="json",
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN


class TestReceptionnerBonCommande:
    """POST /api/bons-commande/<id>/receptionner/"""

    def test_reception_partielle(
        self, api_gestionnaire, bon_commande_brouillon, medicament
    ):
        # D'abord envoyer le BC
        api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/envoyer/"
        )
        ligne_id = bon_commande_brouillon.lignes.first().id
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/receptionner/",
            data={
                "lignes": [
                    {
                        "ligne_id": str(ligne_id),
                        "quantite_recue": 5,
                        "numero_lot": "LOT-REC-001",
                        "date_peremption": "2027-12-31",
                    }
                ]
            },
            format="json",
        )
        assert rep.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )

    def test_reception_bc_non_envoye_retourne_erreur(
        self, api_gestionnaire, bon_commande_brouillon, medicament
    ):
        # BC encore en brouillon → réception impossible
        ligne_id = bon_commande_brouillon.lignes.first().id
        rep = api_gestionnaire.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/receptionner/",
            data={
                "lignes": [
                    {
                        "ligne_id": str(ligne_id),
                        "quantite_recue": 10,
                        "numero_lot": "LOT-001",
                        "date_peremption": "2027-01-01",
                    }
                ]
            },
            format="json",
        )
        assert rep.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_409_CONFLICT,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def test_caissier_bloque_403(
        self, api_caissier, bon_commande_brouillon
    ):
        rep = api_caissier.post(
            f"/api/bons-commande/{bon_commande_brouillon.id}/receptionner/",
            data={"lignes": []},
            format="json",
        )
        assert rep.status_code == status.HTTP_403_FORBIDDEN


class TestDetailBonCommande:
    """GET /api/bons-commande/<id>/"""

    def test_detail_accessible_au_gestionnaire(
        self, api_gestionnaire, bon_commande_brouillon
    ):
        rep = api_gestionnaire.get(
            f"/api/bons-commande/{bon_commande_brouillon.id}/"
        )
        assert rep.status_code == status.HTTP_200_OK
        data = rep.json()
        assert "lignes" in data
        assert data["statut"] == "brouillon"

    def test_bc_inexistant_retourne_404(self, api_gestionnaire):
        rep = api_gestionnaire.get(f"/api/bons-commande/{uuid.uuid4()}/")
        assert rep.status_code == status.HTTP_404_NOT_FOUND
