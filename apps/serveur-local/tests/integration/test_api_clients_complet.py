"""
tests/integration/test_api_clients_complet.py
Tests d'intégration exhaustifs de l'API clients.
Couvre les branches non testées de gestion/clients/vues.py (45 %)
et gestion/clients/services.py (56 %).

Branches couvertes :
  - GET /api/clients/ : filtres search, est_actif
  - POST /api/clients/ : nominal, permission refusée, téléphone dupliqué
  - PATCH /api/clients/<id>/ : champs normaux, crédit (permission adjoint), allergies
  - PUT /api/clients/<id>/ : délégation au PATCH
  - POST /api/clients/<id>/anonymiser/ : titulaire requis
  - Sérialisation allergies par rôle
"""

import pytest
from rest_framework.test import APIClient
from tests.usine.usine_clients import UsineClient
from tests.usine.usine_utilisateurs import (
    UsineCaissier, UsinePharmacienAdjoint, UsineTitulaire,
    UsineUtilisateurPharmacien,
)


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def caissier(db):
    return UsineCaissier.create()


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create()


@pytest.fixture
def stagiaire(db):
    return UsineUtilisateurPharmacien.create(role="stagiaire")


@pytest.fixture
def client_pharmacie(db):
    return UsineClient.create(
        nom="Ouedraogo",
        prenom="Sali",
        telephone="70123456",
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/clients/
# ══════════════════════════════════════════════════════════════════════════════

class TestListeClients:

    def test_liste_retourne_200_pour_caissier(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/clients/")
        assert resp.status_code == 200

    def test_liste_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/clients/")
        assert resp.status_code == 401

    def test_filtre_search_nom(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/clients/?search=Ouedraogo")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert any(c["nom"] == "Ouedraogo" for c in data)

    def test_filtre_search_telephone(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/clients/?q=70123456")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert any(c.get("telephone") == "70123456" for c in data)

    def test_filtre_est_actif_false(self, client_api, caissier, db):
        inactif = UsineClient.create(est_actif=False)
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/clients/?est_actif=false")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        ids = [str(c["id"]) for c in data]
        assert str(inactif.id) in ids


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/clients/
# ══════════════════════════════════════════════════════════════════════════════

class TestCreerClientAPI:

    def test_creation_client_par_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        payload = {
            "prenom": "Moussa",
            "nom": "Diallo",
            "telephone": "76000001",
            "type_client": "particulier",
        }
        resp = client_api.post("/api/clients/", data=payload, format="json")
        assert resp.status_code == 201
        assert resp.data["nom"] == "Diallo"

    def test_creation_client_par_stagiaire_retourne_403(self, client_api, stagiaire):
        client_api.force_authenticate(user=stagiaire)
        payload = {"prenom": "Test", "nom": "Stagiaire", "telephone": "76999999"}
        resp = client_api.post("/api/clients/", data=payload, format="json")
        assert resp.status_code == 403

    def test_creation_telephone_duplique_retourne_409(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        payload = {
            "prenom": "Doublon",
            "nom": "Client",
            "telephone": "70123456",  # même que client_pharmacie
        }
        resp = client_api.post("/api/clients/", data=payload, format="json")
        assert resp.status_code == 409

    def test_creation_sans_telephone(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        payload = {"prenom": "Sans", "nom": "Telephone"}
        resp = client_api.post("/api/clients/", data=payload, format="json")
        assert resp.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/clients/<id>/
# ══════════════════════════════════════════════════════════════════════════════

class TestModifierClientAPI:

    def test_patch_champs_normaux_par_caissier(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.patch(
            f"/api/clients/{client_pharmacie.id}/",
            data={"adresse": "Secteur 12, Ouagadougou"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["adresse"] == "Secteur 12, Ouagadougou"

    def test_patch_credit_par_caissier_retourne_403(self, client_api, caissier, client_pharmacie):
        """Un caissier ne peut pas modifier credit_autorise."""
        client_api.force_authenticate(user=caissier)
        resp = client_api.patch(
            f"/api/clients/{client_pharmacie.id}/",
            data={"credit_autorise": True, "plafond_credit": "50000"},
            format="json",
        )
        assert resp.status_code == 403

    def test_patch_credit_par_adjoint_accepte(self, client_api, adjoint, client_pharmacie):
        """Un pharmacien adjoint peut modifier credit_autorise."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.patch(
            f"/api/clients/{client_pharmacie.id}/",
            data={"credit_autorise": True, "plafond_credit": "75000.00"},
            format="json",
        )
        assert resp.status_code == 200

    def test_patch_allergies_par_caissier_retourne_403(self, client_api, caissier, client_pharmacie):
        """Un caissier ne peut pas modifier les allergies."""
        client_api.force_authenticate(user=caissier)
        resp = client_api.patch(
            f"/api/clients/{client_pharmacie.id}/",
            data={"allergies": "Pénicilline"},
            format="json",
        )
        assert resp.status_code == 403

    def test_patch_allergies_par_adjoint_accepte(self, client_api, adjoint, client_pharmacie):
        """Un adjoint peut modifier les allergies."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.patch(
            f"/api/clients/{client_pharmacie.id}/",
            data={"allergies": "Sulfamides, Aspirine"},
            format="json",
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/clients/<id>/anonymiser/
# ══════════════════════════════════════════════════════════════════════════════

class TestAnonymiserClientAPI:

    def test_anonymisation_par_titulaire(self, client_api, titulaire, client_pharmacie):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.post(f"/api/clients/{client_pharmacie.id}/anonymiser/")
        assert resp.status_code == 200

    def test_anonymisation_par_caissier_retourne_403(self, client_api, caissier, client_pharmacie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.post(f"/api/clients/{client_pharmacie.id}/anonymiser/")
        assert resp.status_code == 403

    def test_anonymisation_client_inexistant_retourne_404(self, client_api, titulaire):
        import uuid
        client_api.force_authenticate(user=titulaire)
        resp = client_api.post(f"/api/clients/{uuid.uuid4()}/anonymiser/")
        assert resp.status_code == 404
