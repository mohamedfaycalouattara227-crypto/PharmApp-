"""
tests/integration/test_api_parametrage_complet.py
Tests d'intégration exhaustifs de l'API paramétrage.
Couvre les branches non testées de gestion/parametrage/vues.py (60 %)
et gestion/parametrage/serialiseurs.py (40 %).

Branches couvertes :
  - GET /api/parametrage/ : tout utilisateur authentifié
  - PATCH /api/parametrage/ : titulaire requis
  - PUT /api/parametrage/ : délégué au PATCH
  - Création automatique du singleton si absent
  - Validation des données invalides
"""

import pytest
from rest_framework.test import APIClient
from tests.usine.usine_utilisateurs import (
    UsineTitulaire, UsineCaissier, UsinePharmacienAdjoint,
)


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create()


@pytest.fixture
def caissier(db):
    return UsineCaissier.create()


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


class TestGetParametrage:

    def test_get_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 401

    def test_get_retourne_200_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 200

    def test_get_retourne_200_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 200

    def test_get_retourne_200_pour_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 200

    def test_get_cree_singleton_si_absent(self, client_api, titulaire):
        """Le GET crée automatiquement le singleton Parametrage s'il n'existe pas."""
        from gestion.parametrage.models import Parametrage
        Parametrage.objects.all().delete()
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 200
        assert Parametrage.objects.count() == 1

    def test_get_contient_champs_obligatoires(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/parametrage/")
        assert resp.status_code == 200
        # Champs attendus dans la réponse
        assert "nom_pharmacie" in resp.data


class TestPatchParametrage:

    def test_patch_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.patch(
            "/api/parametrage/",
            data={"nom_pharmacie": "Hack"},
            format="json",
        )
        assert resp.status_code == 403

    def test_patch_retourne_403_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.patch(
            "/api/parametrage/",
            data={"nom_pharmacie": "Hack"},
            format="json",
        )
        assert resp.status_code == 403

    def test_patch_nom_pharmacie_par_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.patch(
            "/api/parametrage/",
            data={"nom_pharmacie": "Pharmacie du Progrès"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["nom_pharmacie"] == "Pharmacie du Progrès"

    def test_patch_seuil_peremption_par_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.patch(
            "/api/parametrage/",
            data={"seuil_peremption_jours": 45},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["seuil_peremption_jours"] == 45

    def test_patch_donnees_invalides_retourne_400(self, client_api, titulaire):
        """Un type invalide (ex. texte pour un champ entier) → 400."""
        client_api.force_authenticate(user=titulaire)
        resp = client_api.patch(
            "/api/parametrage/",
            data={"seuil_peremption_jours": "pas_un_nombre"},
            format="json",
        )
        assert resp.status_code == 400

    def test_put_delegue_au_patch(self, client_api, titulaire):
        """PUT doit déléguer à PATCH et fonctionner comme lui."""
        client_api.force_authenticate(user=titulaire)
        resp = client_api.put(
            "/api/parametrage/",
            data={"nom_pharmacie": "Pharmacie PUT"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["nom_pharmacie"] == "Pharmacie PUT"
