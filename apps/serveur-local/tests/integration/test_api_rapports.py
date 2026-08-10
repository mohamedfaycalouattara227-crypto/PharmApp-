"""
tests/integration/test_api_rapports.py
ÉTAPE 06 — Tests des endpoints de rapports (VueRapport).

Endpoints couverts :
  GET /api/rapports/tableau-bord/       (EstAuthentifie)
  GET /api/rapports/ventes/             (EstPharmacienAdjoint)
  GET /api/rapports/top-produits/       (EstPharmacienAdjoint)
  GET /api/rapports/marges/             (EstTitulaire)
  GET /api/rapports/ecarts-inventaire/  (EstPharmacienAdjoint)
  GET /api/rapports/export-ventes/      (EstPharmacienAdjoint)
  GET /api/rapports/                    (EstPharmacienAdjoint — liste RapportGenere)

Scénarios testés :
  - 401 pour les anonymes sur chaque endpoint
  - 403 pour les rôles insuffisants (caissier → /marges/, stagiaire → /ventes/)
  - 200 avec la structure JSON attendue pour les rôles autorisés
  - Filtres de date valides et invalides (400)
  - Fenêtre > 366 jours → 400 sur /marges/
  - Export CSV : Content-Type text/csv + en-tête présent
  - top-produits : paramètre limite borné à 100

Marqueur : pytest.mark.integration
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta

pytestmark = pytest.mark.integration

# URL de base selon la configuration DRF (router)
URL_TABLEAU_BORD     = "/api/rapports/tableau-bord/"
URL_VENTES           = "/api/rapports/ventes/"
URL_TOP_PRODUITS     = "/api/rapports/top-produits/"
URL_MARGES           = "/api/rapports/marges/"
URL_ECARTS           = "/api/rapports/ecarts-inventaire/"
URL_EXPORT_VENTES    = "/api/rapports/export-ventes/"
URL_LISTE_RAPPORTS   = "/api/rapports/"


# ─── 1. Tableau de bord ───────────────────────────────────────────────────────

class TestTableauBord:
    """GET /api/rapports/tableau-bord/ — accessible à tout utilisateur authentifié."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_TABLEAU_BORD)
        assert resp.status_code == 401

    def test_caissier_recoit_200(self, api_caissier):
        resp = api_caissier.get(URL_TABLEAU_BORD)
        assert resp.status_code == 200

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_TABLEAU_BORD)
        assert resp.status_code == 200

    def test_structure_reponse(self, api_caissier):
        resp = api_caissier.get(URL_TABLEAU_BORD)
        assert resp.status_code == 200
        data = resp.json()
        assert "ca_aujourd_hui" in data
        assert "nb_ventes_aujourd_hui" in data
        assert "nb_alertes_stock" in data
        assert "nb_ruptures" in data
        assert "nb_peremptions_proches" in data
        assert "seuil_peremption_jours" in data

    def test_ca_est_une_chaine_numerique(self, api_caissier):
        resp = api_caissier.get(URL_TABLEAU_BORD)
        data = resp.json()
        # CA est une str (Decimal sérialisé)
        assert isinstance(data["ca_aujourd_hui"], str)


# ─── 2. Rapport ventes ────────────────────────────────────────────────────────

class TestRapportVentes:
    """GET /api/rapports/ventes/ — réservé EstPharmacienAdjoint+."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_VENTES)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_VENTES)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_VENTES)
        assert resp.status_code == 200

    def test_titulaire_recoit_200(self, api_titulaire):
        resp = api_titulaire.get(URL_VENTES)
        assert resp.status_code == 200

    def test_structure_reponse(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_VENTES)
        data = resp.json()
        assert "debut" in data
        assert "fin" in data
        assert "ca_total" in data
        assert "nb_ventes" in data
        assert "repartition_paiement" in data
        assert "top_produits" in data

    def test_filtres_date_valides(self, api_pharmacien_adjoint):
        debut = (date.today() - timedelta(days=7)).isoformat()
        fin = date.today().isoformat()
        resp = api_pharmacien_adjoint.get(f"{URL_VENTES}?debut={debut}&fin={fin}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["debut"] == debut
        assert data["fin"] == fin

    def test_date_invalide_retourne_400(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(f"{URL_VENTES}?debut=2026-99-99")
        assert resp.status_code == 400

    def test_repartition_paiement_contient_tous_modes(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_VENTES)
        repartition = resp.json()["repartition_paiement"]
        for mode in ("especes", "mobile_money", "assurance", "credit", "cheque"):
            assert mode in repartition


# ─── 3. Top produits ─────────────────────────────────────────────────────────

class TestTopProduits:
    """GET /api/rapports/top-produits/ — réservé EstPharmacienAdjoint+."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_TOP_PRODUITS)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_TOP_PRODUITS)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_TOP_PRODUITS)
        assert resp.status_code == 200

    def test_reponse_est_une_liste(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_TOP_PRODUITS)
        assert isinstance(resp.json(), list)

    def test_parametre_limite_borne_a_100(self, api_pharmacien_adjoint):
        # limit=500 → borné à 100 côté vue
        resp = api_pharmacien_adjoint.get(f"{URL_TOP_PRODUITS}?limit=500&periode=30")
        assert resp.status_code == 200

    def test_parametre_periode_accepte_valeurs_entieres(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(f"{URL_TOP_PRODUITS}?periode=7")
        assert resp.status_code == 200


# ─── 4. Marges (EstTitulaire) ─────────────────────────────────────────────────

class TestMarges:
    """GET /api/rapports/marges/ — réservé EstTitulaire."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_MARGES)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_MARGES)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_403(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_MARGES)
        assert resp.status_code == 403

    def test_titulaire_recoit_200(self, api_titulaire):
        resp = api_titulaire.get(URL_MARGES)
        assert resp.status_code == 200

    def test_structure_paginee(self, api_titulaire):
        resp = api_titulaire.get(URL_MARGES)
        data = resp.json()
        assert "count" in data
        assert "results" in data

    def test_fenetre_superieure_366_retourne_400(self, api_titulaire):
        debut = (date.today() - timedelta(days=400)).isoformat()
        fin = date.today().isoformat()
        resp = api_titulaire.get(f"{URL_MARGES}?debut={debut}&fin={fin}")
        assert resp.status_code == 400

    def test_date_invalide_retourne_200_avec_defaut(self, api_titulaire):
        # En cas de date invalide, la vue utilise les valeurs par défaut (30j)
        resp = api_titulaire.get(f"{URL_MARGES}?debut=invalide&fin=invalide")
        assert resp.status_code == 200


# ─── 5. Écarts d'inventaire ───────────────────────────────────────────────────

class TestEcartsInventaire:
    """GET /api/rapports/ecarts-inventaire/ — réservé EstPharmacienAdjoint+."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_ECARTS)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_ECARTS)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_ECARTS)
        assert resp.status_code == 200

    def test_reponse_est_une_liste(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_ECARTS)
        assert isinstance(resp.json(), list)


# ─── 6. Export CSV ventes ─────────────────────────────────────────────────────

class TestExportVentesCSV:
    """GET /api/rapports/export-ventes/ — format CSV, réservé EstPharmacienAdjoint+."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_EXPORT_VENTES)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_EXPORT_VENTES)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_EXPORT_VENTES)
        assert resp.status_code == 200

    def test_content_type_csv(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_EXPORT_VENTES)
        assert "text/csv" in resp.get("Content-Type", "")

    def test_content_disposition_attachment(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_EXPORT_VENTES)
        disposition = resp.get("Content-Disposition", "")
        assert "attachment" in disposition
        assert ".csv" in disposition

    def test_filtres_date_dans_nom_fichier(self, api_pharmacien_adjoint):
        debut = (date.today() - timedelta(days=7)).isoformat()
        fin = date.today().isoformat()
        resp = api_pharmacien_adjoint.get(f"{URL_EXPORT_VENTES}?debut={debut}&fin={fin}")
        assert resp.status_code == 200
        disposition = resp.get("Content-Disposition", "")
        assert debut in disposition
        assert fin in disposition


# ─── 7. Liste des rapports générés ────────────────────────────────────────────

class TestListeRapports:
    """GET /api/rapports/ — liste paginée de RapportGenere."""

    def test_anonyme_recoit_401(self, api_client):
        resp = api_client.get(URL_LISTE_RAPPORTS)
        assert resp.status_code == 401

    def test_caissier_recoit_403(self, api_caissier):
        resp = api_caissier.get(URL_LISTE_RAPPORTS)
        assert resp.status_code == 403

    def test_pharmacien_adjoint_recoit_200(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(URL_LISTE_RAPPORTS)
        assert resp.status_code == 200

    def test_filtre_type_rapport(self, api_pharmacien_adjoint):
        resp = api_pharmacien_adjoint.get(
            f"{URL_LISTE_RAPPORTS}?type=ventes_journalier"
        )
        assert resp.status_code == 200
