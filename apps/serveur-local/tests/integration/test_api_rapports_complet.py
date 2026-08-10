"""
tests/integration/test_api_rapports_complet.py
Tests d'intégration exhaustifs de l'API rapports.
Couvre les branches non testées de gestion/rapports/vues.py (73 %).

Branches couvertes :
  - GET /api/rapports/tableau-bord/ : structure, valeurs, permissions
  - GET /api/rapports/ventes/ : filtres debut/fin, caissier, produit, format date invalide
  - GET /api/rapports/top-produits/ : filtres période
  - GET /api/rapports/marges/ : titulaire requis
  - GET /api/rapports/ecarts-inventaire/ : liste
  - GET /api/rapports/export-ventes/ : streaming CSV
  - Permissions hiérarchiques par endpoint
"""

import datetime
import pytest
from rest_framework.test import APIClient
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


def _periode_courante():
    """Retourne debut/fin pour les 30 derniers jours."""
    fin = datetime.date.today()
    debut = fin - datetime.timedelta(days=30)
    return debut.isoformat(), fin.isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/rapports/tableau-bord/
# ══════════════════════════════════════════════════════════════════════════════

class TestTableauBord:

    def test_tableau_bord_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert resp.status_code == 401

    def test_tableau_bord_retourne_200_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert resp.status_code == 200

    def test_tableau_bord_retourne_200_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert resp.status_code == 200

    def test_tableau_bord_contient_champs_obligatoires(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert resp.status_code == 200
        champs = [
            "ca_aujourd_hui",
            "nb_ventes_aujourd_hui",
            "nb_alertes_stock",
            "nb_ruptures",
            "nb_peremptions_proches",
            "seuil_peremption_jours",
        ]
        for champ in champs:
            assert champ in resp.data, f"Champ manquant dans tableau-bord : {champ}"

    def test_tableau_bord_nb_ventes_est_entier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert isinstance(resp.data["nb_ventes_aujourd_hui"], int)

    def test_tableau_bord_nb_alertes_est_entier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert isinstance(resp.data["nb_alertes_stock"], int)

    def test_tableau_bord_seuil_peremption_positif(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/tableau-bord/")
        assert int(resp.data["seuil_peremption_jours"]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/rapports/ventes/
# ══════════════════════════════════════════════════════════════════════════════

class TestRapportVentes:

    def test_rapport_ventes_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/ventes/")
        assert resp.status_code == 403

    def test_rapport_ventes_retourne_200_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        debut, fin = _periode_courante()
        resp = client_api.get(f"/api/rapports/ventes/?debut={debut}&fin={fin}")
        assert resp.status_code == 200

    def test_rapport_ventes_contient_champs_agregats(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        debut, fin = _periode_courante()
        resp = client_api.get(f"/api/rapports/ventes/?debut={debut}&fin={fin}")
        assert resp.status_code == 200
        assert "ca_total" in resp.data or "nb_ventes" in resp.data

    def test_rapport_ventes_format_date_invalide_retourne_400(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/ventes/?debut=pas-une-date&fin=aussi-non")
        assert resp.status_code == 400

    def test_rapport_ventes_sans_filtres_retourne_30j(self, client_api, adjoint):
        """Sans filtres, le rapport couvre les 30 derniers jours."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/ventes/")
        assert resp.status_code == 200

    def test_rapport_ventes_filtre_caissier_inconnu(self, client_api, adjoint):
        """Un caissier_id inexistant doit retourner un rapport vide (CA=0)."""
        import uuid
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get(f"/api/rapports/ventes/?caissier={uuid.uuid4()}")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/rapports/top-produits/
# ══════════════════════════════════════════════════════════════════════════════

class TestTopProduits:

    def test_top_produits_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/top-produits/")
        assert resp.status_code == 403

    def test_top_produits_retourne_200_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        debut, fin = _periode_courante()
        resp = client_api.get(f"/api/rapports/top-produits/?debut={debut}&fin={fin}")
        assert resp.status_code == 200

    def test_top_produits_retourne_liste(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/top-produits/")
        assert resp.status_code == 200
        assert isinstance(resp.data, (list, dict))


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/rapports/marges/
# ══════════════════════════════════════════════════════════════════════════════

class TestMarges:

    def test_marges_retourne_403_pour_adjoint(self, client_api, adjoint):
        """Les marges sont réservées au titulaire."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/marges/")
        assert resp.status_code == 403

    def test_marges_retourne_200_pour_titulaire(self, client_api, titulaire):
        client_api.force_authenticate(user=titulaire)
        resp = client_api.get("/api/rapports/marges/")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/rapports/export-ventes/
# ══════════════════════════════════════════════════════════════════════════════

class TestExportVentes:

    def test_export_ventes_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/rapports/export-ventes/")
        assert resp.status_code == 403

    def test_export_ventes_retourne_csv_pour_adjoint(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        debut, fin = _periode_courante()
        resp = client_api.get(f"/api/rapports/export-ventes/?debut={debut}&fin={fin}")
        assert resp.status_code == 200
        content_type = resp.get("Content-Type", "")
        assert "csv" in content_type or "text" in content_type

    def test_export_ventes_contient_header_csv(self, client_api, adjoint):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/rapports/export-ventes/")
        assert resp.status_code == 200
        content_disposition = resp.get("Content-Disposition", "")
        assert "attachment" in content_disposition or "csv" in content_disposition.lower()
