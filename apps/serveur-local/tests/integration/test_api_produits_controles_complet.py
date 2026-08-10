"""
tests/integration/test_api_produits_controles_complet.py
Tests d'intégration exhaustifs des produits contrôlés.
Couvre les branches non testées de gestion/produits_controles/vues.py (15 %).

Branches couvertes :
  - GET /api/produits-controles/ : filtres medicament, date_debut, date_fin, type_mouvement
  - POST /api/produits-controles/ : création d'une entrée registre
  - DELETE /api/produits-controles/<id>/ : interdit (405)
  - PUT /api/produits-controles/<id>/ : interdit (405)
  - PATCH /api/produits-controles/<id>/ : interdit (405)
  - GET /api/produits-controles/export-registre/ : PDF ou CSV si reportlab absent
  - Permissions : pharmacien_adjoint requis, caissier → 403
"""

import datetime
import pytest
from rest_framework.test import APIClient
from tests.usine.usine_medicaments import UsineMedicamentControle, UsineLot
from tests.usine.usine_utilisateurs import (
    UsinePharmacienAdjoint, UsineCaissier, UsineTitulaire,
)


@pytest.fixture
def client_api():
    return APIClient()


@pytest.fixture
def adjoint(db):
    return UsinePharmacienAdjoint.create()


@pytest.fixture
def caissier(db):
    return UsineCaissier.create()


@pytest.fixture
def titulaire(db):
    return UsineTitulaire.create()


@pytest.fixture
def medicament_controle(db):
    return UsineMedicamentControle.create()


@pytest.fixture
def lot_controle(db, medicament_controle):
    return UsineLot.create(medicament=medicament_controle, quantite_disponible=50)


@pytest.fixture
def entree_registre(db, adjoint, medicament_controle, lot_controle):
    """Crée une entrée du registre directement en base."""
    from gestion.produits_controles.models import RegistreProduitControle
    return RegistreProduitControle.objects.create(
        medicament=medicament_controle,
        lot=lot_controle,
        type_mouvement="sortie_vente",
        quantite_mouvement=2,
        unite="comprime",
        stock_avant=50,
        stock_apres=48,
        effectue_par=adjoint,
        supervise_par=adjoint,
        patient_nom="Ibrahima Sawadogo",
        prescripteur_nom="Dr. Kone",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Permissions de base
# ══════════════════════════════════════════════════════════════════════════════

class TestPermissionsProduitControle:

    def test_liste_retourne_401_sans_auth(self, client_api):
        resp = client_api.get("/api/produits-controles/")
        assert resp.status_code == 401

    def test_liste_retourne_403_pour_caissier(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/produits-controles/")
        assert resp.status_code == 403

    def test_liste_retourne_200_pour_adjoint(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/produits-controles/")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/produits-controles/ — filtres
# ══════════════════════════════════════════════════════════════════════════════

class TestFiltresRegistre:

    def test_filtre_par_medicament(self, client_api, adjoint, entree_registre, medicament_controle):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get(f"/api/produits-controles/?medicament={medicament_controle.id}")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert len(data) >= 1

    def test_filtre_date_debut(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        resp = client_api.get(f"/api/produits-controles/?date_debut={hier}")
        assert resp.status_code == 200

    def test_filtre_date_fin(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = client_api.get(f"/api/produits-controles/?date_fin={demain}")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        ids = [str(e["id"]) for e in data]
        assert str(entree_registre.id) in ids

    def test_filtre_type_mouvement(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/produits-controles/?type_mouvement=sortie_vente")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert any(e.get("type_mouvement") == "sortie_vente" for e in data)

    def test_filtre_type_mouvement_inconnu_retourne_liste_vide(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/produits-controles/?type_mouvement=inexistant")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert len(data) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Immutabilité du registre
# ══════════════════════════════════════════════════════════════════════════════

class TestImmuabiliteRegistre:

    def test_delete_retourne_405(self, client_api, adjoint, entree_registre):
        """La suppression d'une entrée registre est interdite (obligation légale)."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.delete(f"/api/produits-controles/{entree_registre.id}/")
        assert resp.status_code == 405
        assert "interdit" in str(resp.data.get("detail", "")).lower() or \
               "interdit" in str(resp.data).lower()

    def test_put_retourne_405(self, client_api, adjoint, entree_registre):
        """La modification PUT est interdite."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.put(
            f"/api/produits-controles/{entree_registre.id}/",
            data={"quantite_mouvement": 999},
            format="json",
        )
        assert resp.status_code == 405

    def test_patch_retourne_405(self, client_api, adjoint, entree_registre):
        """La modification PATCH est interdite."""
        client_api.force_authenticate(user=adjoint)
        resp = client_api.patch(
            f"/api/produits-controles/{entree_registre.id}/",
            data={"quantite_mouvement": 999},
            format="json",
        )
        assert resp.status_code == 405


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/produits-controles/
# ══════════════════════════════════════════════════════════════════════════════

class TestCreerEntreeRegistre:

    def test_creation_par_adjoint_retourne_201(
        self, client_api, adjoint, medicament_controle, lot_controle
    ):
        client_api.force_authenticate(user=adjoint)
        payload = {
            "medicament": str(medicament_controle.id),
            "lot": str(lot_controle.id),
            "type_mouvement": "sortie_vente",
            "quantite_mouvement": 1,
            "unite": "comprime",
            "supervise_par": str(adjoint.id),
            "patient_nom": "Patient Test",
        }
        resp = client_api.post("/api/produits-controles/", data=payload, format="json")
        assert resp.status_code == 201, resp.data

    def test_creation_par_caissier_retourne_403(
        self, client_api, caissier, medicament_controle, lot_controle
    ):
        client_api.force_authenticate(user=caissier)
        payload = {
            "medicament": str(medicament_controle.id),
            "lot": str(lot_controle.id),
            "type_mouvement": "sortie_vente",
            "quantite_mouvement": 1,
            "unite": "comprime",
        }
        resp = client_api.post("/api/produits-controles/", data=payload, format="json")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/produits-controles/export-registre/
# ══════════════════════════════════════════════════════════════════════════════

class TestExportRegistre:

    def test_export_retourne_200_pour_adjoint(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        resp = client_api.get("/api/produits-controles/export-registre/")
        # Peut retourner PDF ou CSV selon la disponibilité de reportlab
        assert resp.status_code == 200
        assert resp["Content-Type"] in (
            "application/pdf",
            "text/csv; charset=utf-8",
        )

    def test_export_avec_filtre_date_retourne_200(self, client_api, adjoint, entree_registre):
        client_api.force_authenticate(user=adjoint)
        hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = client_api.get(
            f"/api/produits-controles/export-registre/?date_debut={hier}&date_fin={demain}"
        )
        assert resp.status_code == 200

    def test_export_caissier_retourne_403(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/produits-controles/export-registre/")
        assert resp.status_code == 403
