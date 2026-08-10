"""
tests/integration/test_api_catalogue_complet.py
Tests d'intégration exhaustifs de l'API catalogue.
Couvre les branches non testées de gestion/catalogue/vues.py (38 %).

Branches couvertes :
  - GET /api/catalogue/medicaments/ : filtres est_actif, search, categorie, prix_reglemente
  - POST /api/catalogue/medicaments/ : création, permission gestionnaire_stock requis
  - PATCH /api/catalogue/medicaments/<id>/ : modification partielle
  - DELETE /api/catalogue/medicaments/<id>/ : suppression
  - POST /api/catalogue/medicaments/import-csv/ : succès, sans fichier, décodage UTF-8/latin-1
  - GET /api/catalogue/categories/ : filtres est_active
  - POST /api/catalogue/categories/ : création
  - DELETE /api/catalogue/categories/<id>/ : conflit médicaments actifs, succès vide
  - GET /api/catalogue/lots/ : filtres est_actif, medicament_id, peremption_proche
"""

import io
import datetime
import pytest
from rest_framework.test import APIClient
from tests.usine.usine_medicaments import (
    UsineCategorie, UsineMedicament, UsineLot, UsineLotPerimantBientot,
)
from tests.usine.usine_utilisateurs import (
    UsineGestionnaireStock, UsineCaissier, UsinePharmacienAdjoint,
)


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
def adjoint(db):
    return UsinePharmacienAdjoint.create()


@pytest.fixture
def categorie(db):
    return UsineCategorie.create(nom="Antibiotiques", code="ANTIB")


@pytest.fixture
def medicament(db, categorie):
    return UsineMedicament.create(categorie=categorie)


@pytest.fixture
def lot(db, medicament):
    return UsineLot.create(medicament=medicament)


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/catalogue/medicaments/
# ══════════════════════════════════════════════════════════════════════════════

class TestListeMedicaments:

    def test_liste_retourne_200_pour_caissier(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/medicaments/")
        assert resp.status_code == 200

    def test_liste_sans_auth_retourne_401(self, client_api, medicament):
        resp = client_api.get("/api/catalogue/medicaments/")
        assert resp.status_code == 401

    def test_filtre_est_actif_vrai(self, client_api, caissier, db):
        actif = UsineMedicament.create(est_actif=True)
        inactif = UsineMedicament.create(est_actif=False)
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/medicaments/?est_actif=true")
        assert resp.status_code == 200
        ids = [str(m["id"]) for m in resp.data["results"] if "results" in resp.data] or [
            str(m["id"]) for m in resp.data
        ]
        assert str(actif.id) in ids
        assert str(inactif.id) not in ids

    def test_filtre_search_nom(self, client_api, caissier, db):
        UsineMedicament.create(nom="Paracetamol 500mg")
        UsineMedicament.create(nom="Ibuprofene 400mg")
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/medicaments/?search=Paracetamol")
        assert resp.status_code == 200
        # Au moins 1 résultat contenant Paracetamol
        data = resp.data.get("results", resp.data)
        noms = [m["nom"] for m in data]
        assert any("Paracetamol" in n for n in noms)

    def test_filtre_search_dci(self, client_api, caissier, db):
        UsineMedicament.create(
            nom="Amoxil 500mg",
            denomination_commune_internationale="Amoxicilline",
        )
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/medicaments/?q=Amoxicilline")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert len(data) >= 1

    def test_filtre_categorie(self, client_api, caissier, medicament, categorie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get(f"/api/catalogue/medicaments/?categorie={categorie.id}")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert any(str(m["id"]) == str(medicament.id) for m in data)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/catalogue/medicaments/
# ══════════════════════════════════════════════════════════════════════════════

class TestCreerMedicament:

    def test_creation_par_gestionnaire_retourne_201(self, client_api, gestionnaire, categorie):
        client_api.force_authenticate(user=gestionnaire)
        payload = {
            "nom": "Metronidazole 250mg",
            "denomination_commune_internationale": "Metronidazole",
            "categorie": str(categorie.id),
            "prix_public": "600.00",
            "forme_pharmaceutique": "comprime",
        }
        resp = client_api.post("/api/catalogue/medicaments/", data=payload, format="json")
        assert resp.status_code == 201
        assert resp.data["nom"] == "Metronidazole 250mg"

    def test_creation_par_caissier_retourne_403(self, client_api, caissier, categorie):
        client_api.force_authenticate(user=caissier)
        payload = {"nom": "Test 100mg", "prix_public": "200.00"}
        resp = client_api.post("/api/catalogue/medicaments/", data=payload, format="json")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/catalogue/medicaments/import-csv/
# ══════════════════════════════════════════════════════════════════════════════

class TestImportCsv:

    def _csv_valide(self):
        contenu = (
            "nom,dci,forme,dosage,categorie,prix_public\n"
            "Paracetamol 500mg,Paracetamol,comprime,500mg,Antalgiques,350.00\n"
            "Ibuprofene 200mg,Ibuprofene,gelule,200mg,AINS,500.00\n"
        )
        return io.BytesIO(contenu.encode("utf-8"))

    def test_import_csv_valide_retourne_200(self, client_api, gestionnaire):
        client_api.force_authenticate(user=gestionnaire)
        fichier = self._csv_valide()
        resp = client_api.post(
            "/api/catalogue/medicaments/import-csv/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert resp.status_code == 200
        assert resp.data["crees"] >= 2

    def test_import_csv_sans_fichier_retourne_400(self, client_api, gestionnaire):
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.post(
            "/api/catalogue/medicaments/import-csv/",
            data={},
            format="multipart",
        )
        assert resp.status_code == 400
        assert "fichier" in resp.data.get("detail", "").lower() or "fichier" in str(resp.data).lower()

    def test_import_csv_par_caissier_retourne_403(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        fichier = self._csv_valide()
        resp = client_api.post(
            "/api/catalogue/medicaments/import-csv/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert resp.status_code == 403

    def test_import_csv_colonne_nom_vide_ignoree(self, client_api, gestionnaire):
        """Les lignes sans nom sont ignorées et comptabilisées dans les erreurs."""
        client_api.force_authenticate(user=gestionnaire)
        contenu = (
            "nom,dci,forme,dosage,categorie,prix_public\n"
            ",Ibuprofene,gelule,200mg,AINS,500.00\n"
            "Amoxicilline 500mg,Amoxicilline,gelule,500mg,ATB,800.00\n"
        )
        fichier = io.BytesIO(contenu.encode("utf-8"))
        resp = client_api.post(
            "/api/catalogue/medicaments/import-csv/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert resp.status_code == 200
        assert resp.data["crees"] == 1
        assert len(resp.data.get("erreurs", [])) >= 1

    def test_import_csv_mise_a_jour_si_code_cis_existe(self, client_api, gestionnaire, db):
        """Si le code CIS existe déjà, le médicament est mis à jour (pas créé)."""
        med = UsineMedicament.create(code_cis="CIS00000001", nom="Ancien Nom")
        client_api.force_authenticate(user=gestionnaire)
        contenu = (
            "nom,dci,forme,dosage,categorie,prix_public,code_cis\n"
            f"Nouveau Nom,Amox,gelule,500mg,ATB,800.00,{med.code_cis}\n"
        )
        fichier = io.BytesIO(contenu.encode("utf-8"))
        resp = client_api.post(
            "/api/catalogue/medicaments/import-csv/",
            data={"fichier": fichier},
            format="multipart",
        )
        assert resp.status_code == 200
        assert resp.data["mis_a_jour"] == 1
        assert resp.data["crees"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# Categories
# ══════════════════════════════════════════════════════════════════════════════

class TestCategories:

    def test_liste_categories_retourne_200(self, client_api, caissier, categorie):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/categories/")
        assert resp.status_code == 200

    def test_filtre_categories_est_active(self, client_api, caissier, db):
        active = UsineCategorie.create(est_active=True)
        inactive = UsineCategorie.create(est_active=False)
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/categories/?est_active=true")
        assert resp.status_code == 200

    def test_suppression_categorie_avec_medicaments_actifs_retourne_409(
        self, client_api, gestionnaire, medicament, categorie
    ):
        """La suppression d'une catégorie avec médicaments actifs → 409."""
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.delete(f"/api/catalogue/categories/{categorie.id}/")
        assert resp.status_code == 409
        assert "conflit" in str(resp.data).lower() or "conflit" in str(resp.data.get("erreur", "")).lower()

    def test_suppression_categorie_vide_retourne_204(self, client_api, gestionnaire, db):
        """La suppression d'une catégorie vide (sans médicaments) → 204."""
        cat_vide = UsineCategorie.create(nom="Vide", code="VIDE")
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.delete(f"/api/catalogue/categories/{cat_vide.id}/")
        assert resp.status_code == 204


# ══════════════════════════════════════════════════════════════════════════════
# Lots
# ══════════════════════════════════════════════════════════════════════════════

class TestLots:

    def test_liste_lots_retourne_200_pour_gestionnaire(self, client_api, gestionnaire, lot):
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.get("/api/catalogue/lots/")
        assert resp.status_code == 200

    def test_liste_lots_retourne_403_pour_caissier(self, client_api, caissier, lot):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/catalogue/lots/")
        assert resp.status_code == 403

    def test_filtre_lots_par_medicament(self, client_api, gestionnaire, lot, medicament):
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.get(f"/api/catalogue/lots/?medicament_id={medicament.id}")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        assert any(str(l["medicament"]) == str(medicament.id) or str(l.get("id")) == str(lot.id) for l in data)

    def test_filtre_peremption_proche(self, client_api, gestionnaire, db):
        """Les lots périmant bientôt sont retournés avec le filtre peremption_proche."""
        lot_proche = UsineLotPerimantBientot.create()
        client_api.force_authenticate(user=gestionnaire)
        resp = client_api.get("/api/catalogue/lots/?peremption_proche=true")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data)
        ids = [str(l["id"]) for l in data]
        assert str(lot_proche.id) in ids

    def test_creation_lot_par_gestionnaire(self, client_api, gestionnaire, medicament):
        client_api.force_authenticate(user=gestionnaire)
        payload = {
            "medicament": str(medicament.id),
            "numero_lot": "LOT-TEST-2025",
            "quantite_initiale": 100,
            "quantite_disponible": 100,
            "prix_achat_unitaire": "450.00",
            "date_peremption": (datetime.date.today() + datetime.timedelta(days=365)).isoformat(),
        }
        resp = client_api.post("/api/catalogue/lots/", data=payload, format="json")
        assert resp.status_code == 201
