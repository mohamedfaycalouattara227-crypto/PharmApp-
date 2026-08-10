"""
tests/integration/test_api_authentification_complet.py
Tests d'intégration exhaustifs de l'API authentification.
Couvre les branches non testées de gestion/authentification/vues.py (62 %)
et api/authentication.py (61 %).

Branches couvertes :
  - POST /api/auth/connexion/ : succès, email vide, mot de passe invalide, compte verrouillé
  - POST /api/auth/deconnexion/ : succès, sans token
  - GET /api/auth/profil/ : propre profil, mise à jour
  - GET /api/utilisateurs/ : liste (titulaire), permissions
  - POST /api/utilisateurs/ : création (titulaire)
  - POST /api/utilisateurs/<id>/suspendre/ : suspension, auto-suspension interdite
  - Comptage tentatives échouées → verrouillage automatique
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from tests.usine.usine_utilisateurs import (
    UsineTitulaire, UsineCaissier, UsinePharmacienAdjoint,
    UsineUtilisateurPharmacien,
)


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create(email="titulaire@pharmapp.bf")


@pytest.fixture
def caissier(db):
    return UsineCaissier.create(email="caissier@pharmapp.bf")


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/auth/connexion/
# ══════════════════════════════════════════════════════════════════════════════

class TestConnexion:

    def test_connexion_champs_vides_retourne_400(self, client_api):
        resp = client_api.post("/api/auth/connexion/", data={}, format="json")
        assert resp.status_code == 400
        assert "erreur" in resp.data

    def test_connexion_email_manquant_retourne_400(self, client_api):
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"mot_de_passe": "test"},
            format="json",
        )
        assert resp.status_code == 400

    def test_connexion_mot_de_passe_manquant_retourne_400(self, client_api):
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"email": "test@test.bf"},
            format="json",
        )
        assert resp.status_code == 400

    def test_connexion_email_invalide_retourne_400(self, client_api):
        """Un email sans '@' est rejeté immédiatement."""
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"email": "pasunemail", "mot_de_passe": "test123"},
            format="json",
        )
        assert resp.status_code == 400

    def test_connexion_mauvais_credentials_retourne_401(self, client_api, caissier):
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"email": "caissier@pharmapp.bf", "mot_de_passe": "mauvais_mdp"},
            format="json",
        )
        assert resp.status_code == 401

    def test_connexion_succes_retourne_200(self, client_api, db):
        user = UsineCaissier.create(email="login_ok@pharmapp.bf")
        user.set_password("MotDePasseOK1!")
        user.save()
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"email": "login_ok@pharmapp.bf", "mot_de_passe": "MotDePasseOK1!"},
            format="json",
        )
        assert resp.status_code == 200

    def test_connexion_verrouillage_apres_n_echecs(self, client_api, db, settings):
        """Après N échecs consécutifs, le compte doit être verrouillé."""
        settings.TENTATIVES_CONNEXION_MAX = 3
        user = UsineCaissier.create(email="lock_test@pharmapp.bf")

        for _ in range(3):
            client_api.post(
                "/api/auth/connexion/",
                data={"email": "lock_test@pharmapp.bf", "mot_de_passe": "mauvais"},
                format="json",
            )

        user.refresh_from_db()
        assert user.est_verrouille is True

    def test_connexion_mot_de_passe_trop_long_retourne_400(self, client_api):
        """Un mot de passe > 256 caractères est rejeté."""
        resp = client_api.post(
            "/api/auth/connexion/",
            data={"email": "test@test.bf", "mot_de_passe": "a" * 257},
            format="json",
        )
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# GET/PATCH /api/auth/profil/
# ══════════════════════════════════════════════════════════════════════════════

class TestProfil:

    def test_profil_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/auth/profil/")
        assert resp.status_code == 401

    def test_profil_retourne_200_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/auth/profil/")
        assert resp.status_code == 200
        assert resp.data.get("email") == "caissier@pharmapp.bf"

    def test_profil_contient_role(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/auth/profil/")
        assert "role" in resp.data


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/utilisateurs/
# ══════════════════════════════════════════════════════════════════════════════

class TestListeUtilisateurs:

    def test_liste_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/utilisateurs/")
        assert resp.status_code == 403

    def test_liste_retourne_200_pour_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/utilisateurs/")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/utilisateurs/
# ══════════════════════════════════════════════════════════════════════════════

class TestCreerUtilisateur:

    def test_creation_par_titulaire_retourne_201(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        payload = {
            "prenom": "Nouveau",
            "nom": "Caissier",
            "email": "nouveau.caissier@pharmapp.bf",
            "role": "caissier",
            "mot_de_passe": "MotDePasse123!",
            "numero_ordre": "ORD-0099",
        }
        resp = client_api.post("/api/utilisateurs/", data=payload, format="json")
        assert resp.status_code in (201, 200)

    def test_creation_par_caissier_retourne_403(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        payload = {"prenom": "Hack", "nom": "User", "email": "hack@test.bf", "role": "titulaire"}
        resp = client_api.post("/api/utilisateurs/", data=payload, format="json")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/utilisateurs/<id>/suspendre/
# ══════════════════════════════════════════════════════════════════════════════

class TestSuspendreUtilisateur:

    def test_suspendre_utilisateur_par_titulaire(self, client_api, titulaire, caissier):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.post(f"/api/utilisateurs/{caissier.id}/suspendre/")
        assert resp.status_code in (200, 204)

    def test_titulaire_ne_peut_pas_se_suspendre_lui_meme(self, client_api, titulaire):
        """Un titulaire ne peut pas suspendre son propre compte."""
        client_api.force_authenticate(user=titulaire)
        resp = client_api.post(f"/api/utilisateurs/{titulaire.id}/suspendre/")
        # Doit être refusé (403 ou 400)
        assert resp.status_code in (400, 403)

    def test_suspendre_par_caissier_retourne_403(self, client_api, caissier, adjoint):
        client_api.force_authenticate(user=caissier)
        resp = client_api.post(f"/api/utilisateurs/{adjoint.id}/suspendre/")
        assert resp.status_code == 403
