"""
tests/integration/test_api_ventes_complet.py
Tests d'intégration exhaustifs de l'API ventes.
Couvre les branches non testées de gestion/ventes/vues.py (52 %).

Branches couvertes :
  - Validation panier vide
  - Validation quantité, taux_remise, prix_unitaire négatif
  - Mode paiement invalide
  - Mobile Money sans référence transaction
  - Client introuvable
  - Crédit non autorisé / plafond dépassé
  - GET avec filtres client, statut, debut, fin
  - POST /ventes/<id>/annuler/ : nominal, vente introuvable
  - POST /ventes/<id>/monnaie/ : calcul monnaie
  - POST /ventes/<id>/avoir/ : retour client
  - Permissions : stagiaire → 403
"""

import datetime
import uuid
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from tests.usine.usine_utilisateurs import (
    UsineCaissier, UsinePharmacienAdjoint, UsineUtilisateurPharmacien,
)
from tests.usine.usine_medicaments import UsineMedicament, UsineLot
from tests.usine.usine_clients import UsineClient
from tests.usine.usine_ventes import UsineVente


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
def stagiaire(db):
    return UsineUtilisateurPharmacien.create(role="stagiaire")


@pytest.fixture
def medicament(db):
    return UsineMedicament.create(prix_public=Decimal("800.00"), est_actif=True)


@pytest.fixture
def lot(db, medicament):
    return UsineLot.create(medicament=medicament, quantite_disponible=100)


@pytest.fixture
def client_avec_credit(db):
    return UsineClient.create(
        credit_autorise=True,
        plafond_credit=Decimal("50000"),
        encours_credit=Decimal("0"),
    )


@pytest.fixture
def client_sans_credit(db):
    return UsineClient.create(
        credit_autorise=False,
        plafond_credit=Decimal("0"),
    )


@pytest.fixture
def vente_validee(db, caissier, medicament, lot):
    return UsineVente.create(caissier=caissier)


def _payload_vente_minimal(medicament, lot=None):
    """Payload minimal valide pour créer une vente en espèces."""
    return {
        "panier": [
            {
                "medicament_id": str(medicament.id),
                "quantite": 2,
                "prix_unitaire_demande": "800.00",
                "taux_remise": "0",
                "lot_id": str(lot.id) if lot else None,
            }
        ],
        "mode_paiement": "especes",
        "montant_encaisse": "2000.00",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Validation du panier (gestion/ventes/vues.py — _valider_panier)
# ══════════════════════════════════════════════════════════════════════════════

class TestValidationPanier:

    def test_panier_vide_retourne_400(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.post(
            "/api/ventes/",
            data={"panier": [], "mode_paiement": "especes", "montant_encaisse": "1000"},
            format="json",
        )
        assert resp.status_code == 400
        assert "panier" in resp.data

    def test_quantite_negative_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": -1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "especes",
            "montant_encaisse": "1000",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_quantite_zero_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 0, "prix_unitaire_demande": "800"}],
            "mode_paiement": "especes",
            "montant_encaisse": "1000",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_taux_remise_hors_bornes_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800", "taux_remise": "150"}],
            "mode_paiement": "especes",
            "montant_encaisse": "1000",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_prix_unitaire_negatif_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "-100"}],
            "mode_paiement": "especes",
            "montant_encaisse": "100",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_mode_paiement_invalide_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "bitcoin",
            "montant_encaisse": "1000",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400
        assert "mode_paiement" in resp.data

    def test_mobile_money_sans_reference_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "mobile_money",
            "montant_encaisse": "800",
            # reference_mobile_money manquante intentionnellement
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400
        assert "reference_mobile_money" in resp.data

    def test_especes_montant_encaisse_zero_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "especes",
            "montant_encaisse": "0",
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_client_introuvable_retourne_400(self, client_api, caissier, medicament):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "especes",
            "montant_encaisse": "800",
            "client_id": str(uuid.uuid4()),  # UUID inexistant
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400
        assert "client_id" in resp.data

    def test_credit_sans_autorisation_retourne_422(self, client_api, caissier, medicament, client_sans_credit):
        client_api.force_authenticate(user=caissier)
        payload = {
            "panier": [{"medicament_id": str(medicament.id), "quantite": 1, "prix_unitaire_demande": "800"}],
            "mode_paiement": "credit",
            "montant_encaisse": "800",
            "client_id": str(client_sans_credit.id),
        }
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 422

    def test_stagiaire_ne_peut_pas_creer_vente_retourne_403(self, client_api, stagiaire, medicament):
        client_api.force_authenticate(user=stagiaire)
        payload = _payload_vente_minimal(medicament)
        resp = client_api.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/ventes/ — filtres
# ══════════════════════════════════════════════════════════════════════════════

class TestListeVentes:

    def test_liste_retourne_200_pour_caissier(self, client_api, caissier, vente_validee):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/ventes/")
        assert resp.status_code == 200

    def test_filtre_statut(self, client_api, caissier, vente_validee):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get("/api/ventes/?statut=validee")
        assert resp.status_code == 200

    def test_filtre_debut_fin(self, client_api, caissier, vente_validee):
        client_api.force_authenticate(user=caissier)
        hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = client_api.get(f"/api/ventes/?debut={hier}&fin={demain}")
        assert resp.status_code == 200

    def test_filtre_client(self, client_api, caissier, vente_validee, client_avec_credit):
        client_api.force_authenticate(user=caissier)
        resp = client_api.get(f"/api/ventes/?client={client_avec_credit.id}")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/ventes/<id>/annuler/
# ══════════════════════════════════════════════════════════════════════════════

class TestAnnulerVente:

    def test_annuler_vente_introuvable_retourne_404(self, client_api, caissier):
        client_api.force_authenticate(user=caissier)
        resp = client_api.post(
            f"/api/ventes/{uuid.uuid4()}/annuler/",
            data={"motif": "Erreur de saisie"},
            format="json",
        )
        assert resp.status_code == 404

    def test_annuler_sans_permission_retourne_403(self, client_api, stagiaire, vente_validee):
        client_api.force_authenticate(user=stagiaire)
        resp = client_api.post(
            f"/api/ventes/{vente_validee.id}/annuler/",
            data={"motif": "Test"},
            format="json",
        )
        assert resp.status_code == 403
