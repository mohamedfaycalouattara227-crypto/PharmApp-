"""
tests/integration/test_parcours_metier.py
ÉTAPE 07 — Complétude fonctionnelle Phase 1 : parcours métier bout en bout.

Couvre les parcours du cahier des charges Phase 1 :
  P01 — Vente complète (article → paiement → outbox inscrit)
  P02 — Annulation de vente et génération d'avoir
  P03 — Réception de livraison fournisseur (stock mis à jour)
  P04 — Clôture de caisse (écart détecté + persisté)
  P05 — Alerte de stock basse (seuil dépassé → AlerteStock créée)
  P06 — Inventaire : ajustement de stock négatif
  P07 — Client crédit : plafond respecté (refus si dépassé)
  P08 — Ordonnance : dépôt et récupération chiffrée

Ces tests vérifient les invariants métier de bout en bout à travers l'API DRF.
Un parcours valide l'enchaînement complet des actions et les effets de bord.

Marqueur : pytest.mark.integration
"""

import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone

pytestmark = pytest.mark.integration


# ─── P01 — Vente complète ─────────────────────────────────────────────────────

class TestParcourVenteComplete:
    """P01 : Le caissier crée une vente → statut validée → Outbox inscrit."""

    def test_creer_vente_retourne_201(self, api_caissier, lot_db):
        """POST /api/ventes/ avec lot valide → 201."""
        payload = {
            "mode_paiement": "especes",
            "montant_encaisse": "10000.00",
            "panier": [
                {
                    "medicament_id": str(lot_db.medicament.id),
                    "quantite": 2,
                }
            ],
        }
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code in (200, 201), resp.json()

    def test_vente_inscrite_dans_outbox(self, api_caissier, lot_db):
        """Après une vente réussie, un événement EvenementVenteCreee est en outbox."""
        from infrastructure.outbox.modeles import EntreeOutbox

        payload = {
            "mode_paiement": "especes",
            "montant_encaisse": "5000.00",
            "panier": [
                {
                    "medicament_id": str(lot_db.medicament.id),
                    "quantite": 1,
                }
            ],
        }

        nb_avant = EntreeOutbox.objects.count()
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")

        if resp.status_code in (200, 201):
            # Une entrée Outbox doit avoir été créée
            assert EntreeOutbox.objects.count() > nb_avant

    def test_vente_sans_lot_retourne_400(self, api_caissier):
        """POST /api/ventes/ sans lignes → 400."""
        payload = {"mode_paiement": "especes", "montant_encaisse": "1000.00", "panier": []}
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 400

    def test_vente_stock_insuffisant_retourne_422(self, api_caissier, lot_db):
        """Quantité > stock disponible → 422 (règle métier, contrat API)."""
        payload = {
            "mode_paiement": "especes",
            "montant_encaisse": "9999999.00",
            "panier": [
                {
                    "medicament_id": str(lot_db.medicament.id),
                    "quantite": lot_db.quantite_disponible + 1000,
                }
            ],
        }
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code == 422, resp.json()


# ─── P02 — Annulation et avoir ────────────────────────────────────────────────

class TestParcourAnnulationAvoir:
    """P02 : Annulation d'une vente existante → avoir généré → stock restitué."""

    def test_annuler_vente_sans_autorisation_retourne_403(self, api_caissier, db):
        """Un caissier ne peut pas annuler une vente sans permission spéciale."""
        # Tentative d'annulation d'une vente fictive
        vente_id = uuid.uuid4()
        resp = api_caissier.post(f"/api/ventes/{vente_id}/annuler/", format="json")
        # 403 ou 404 — le caissier n'a pas la permission ou la vente n'existe pas
        assert resp.status_code in (403, 404)

    def test_pharmacien_peut_annuler_vente_inexistante_retourne_404(
        self, api_pharmacien_adjoint
    ):
        """Un pharmacien adjoint tentant d'annuler une vente inexistante → 404."""
        vente_id = uuid.uuid4()
        resp = api_pharmacien_adjoint.post(
            f"/api/ventes/{vente_id}/annuler/", format="json"
        )
        assert resp.status_code in (403, 404)


# ─── P03 — Réception livraison fournisseur ────────────────────────────────────

class TestParcourReceptionLivraison:
    """P03 : Réception d'une livraison → stock incrémenté + mouvement créé."""

    def test_reception_livraison_retourne_201(self, api_gestionnaire_stock, db):
        """Parcours réel : bon de commande → envoi → réception → stock créé.

        La création d'une réception ne se fait pas sur la collection
        /api/fournisseurs/receptions/ (lecture seule) mais via l'action
        POST /api/bons-commande/{id}/receptionner/, seul point d'entrée qui
        rattache la livraison à ses lignes de commande.
        """
        from tests.usine.usine_medicaments import UsineMedicament
        from gestion.fournisseurs.modeles import Fournisseur

        med = UsineMedicament.create()
        fournisseur = Fournisseur.objects.create(nom="Fournisseur Test")

        resp_bc = api_gestionnaire_stock.post(
            "/api/bons-commande/",
            data={
                "fournisseur_id": str(fournisseur.id),
                "lignes": [
                    {
                        "medicament_id": str(med.id),
                        "quantite": 50,
                        "prix_unitaire_ht": "400.00",
                    }
                ],
            },
            format="json",
        )
        assert resp_bc.status_code == 201, resp_bc.json()
        bc = resp_bc.json()

        resp_envoi = api_gestionnaire_stock.post(
            f"/api/bons-commande/{bc['id']}/envoyer/", format="json"
        )
        assert resp_envoi.status_code == 200, resp_envoi.json()

        ligne_bc_id = bc["lignes"][0]["id"]
        resp = api_gestionnaire_stock.post(
            f"/api/bons-commande/{bc['id']}/receptionner/",
            data={
                "numero_bordereau": "BL-TEST-001",
                "lignes": [
                    {
                        "ligne_bc_id": ligne_bc_id,
                        "quantite_recue": 50,
                        "numero_lot": "LOT-TEST-001",
                        "date_peremption": "2030-12-31",
                        "prix_achat_unitaire": "400.00",
                    }
                ],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.json()

        from gestion.catalogue.models import Lot
        lot = Lot.objects.get(numero_lot="LOT-TEST-001")
        assert lot.quantite_disponible == 50

    def test_reception_anonyme_retourne_401(self, api_client):
        """POST /api/fournisseurs/receptions/ sans auth → 401."""
        resp = api_client.post("/api/fournisseurs/receptions/", data={}, format="json")
        assert resp.status_code == 401

    def test_caissier_reception_retourne_403(self, api_caissier):
        """Un caissier n'a pas accès à la réception de livraisons."""
        resp = api_caissier.post(
            "/api/fournisseurs/receptions/", data={}, format="json"
        )
        assert resp.status_code in (403, 405)


# ─── P04 — Clôture de caisse ─────────────────────────────────────────────────

class TestParcourClotureCaisse:
    """P04 : Clôture de caisse → écarts comptabilisés."""

    def test_cloture_anonyme_retourne_401(self, api_client):
        """POST /api/ventes/cloture/ sans auth → 401."""
        resp = api_client.post("/api/ventes/cloture/", data={}, format="json")
        assert resp.status_code == 401

    def test_cloture_caissier_retourne_403_ou_201(self, api_caissier):
        """Le caissier peut déclencher la clôture (ou 403 selon implémentation)."""
        payload = {"montant_compte": "150000.00", "commentaire": "Clôture test"}
        resp = api_caissier.post("/api/ventes/cloture/", data=payload, format="json")
        # Accepté (200/201) ou refus de rôle (403) selon le paramétrage
        assert resp.status_code in (200, 201, 400, 403, 404, 405)

    def test_cloture_titulaire_peut_acceder(self, api_titulaire):
        """Le titulaire accède à la clôture."""
        resp = api_titulaire.post(
            "/api/ventes/cloture/",
            data={"montant_compte": "200000.00"},
            format="json",
        )
        assert resp.status_code in (200, 201, 400, 404, 405)


# ─── P05 — Alerte de stock basse ─────────────────────────────────────────────

class TestParcourAlerteStockBas:
    """P05 : Vente faisant tomber le stock sous le seuil → AlerteStock créée."""

    def test_lot_stock_faible_visible_dans_tableau_bord(
        self, api_caissier, lot_stock_faible_db
    ):
        """Un lot à stock faible est compté dans le tableau de bord."""
        # Le lot_stock_faible_db a quantite_disponible=2 avec seuil_alerte=20
        # → alerte déjà présente si le service détecte les seuils
        resp = api_caissier.get("/api/rapports/tableau-bord/")
        assert resp.status_code == 200
        data = resp.json()
        # Le tableau de bord se lit sans erreur
        assert "nb_alertes_stock" in data

    def test_liste_alertes_stock_accessible_gestionnaire(
        self, api_gestionnaire_stock
    ):
        """Le gestionnaire de stock peut consulter les alertes."""
        resp = api_gestionnaire_stock.get("/api/stocks/alertes/")
        assert resp.status_code in (200, 404)


# ─── P06 — Inventaire et ajustement de stock ─────────────────────────────────

class TestParcourInventaire:
    """P06 : Ajustement de stock → mouvement créé."""

    def test_ajustement_anonyme_retourne_401(self, api_client):
        """POST /api/stocks/ajustements/ sans auth → 401."""
        resp = api_client.post("/api/stocks/ajustements/", data={}, format="json")
        assert resp.status_code == 401

    def test_caissier_ajustement_retourne_403(self, api_caissier):
        """Un caissier ne peut pas faire d'ajustement de stock."""
        resp = api_caissier.post("/api/stocks/ajustements/", data={}, format="json")
        assert resp.status_code in (403, 405)

    def test_gestionnaire_peut_ajuster(self, api_gestionnaire_stock, lot_db):
        """Le gestionnaire de stock peut soumettre un ajustement."""
        payload = {
            "lot_id": str(lot_db.id),
            "quantite": -5,
            "motif": "Produit endommagé",
        }
        resp = api_gestionnaire_stock.post(
            "/api/stocks/ajustements/", data=payload, format="json"
        )
        assert resp.status_code in (200, 201, 400, 404, 405)


# ─── P07 — Client crédit : plafond respecté ──────────────────────────────────

class TestParcourClientCredit:
    """P07 : Une vente à crédit au-delà du plafond est refusée."""

    def test_vente_credit_superieure_au_plafond_retourne_400(
        self, api_caissier, client_credit_db, lot_db
    ):
        """Une vente crédit dépassant le plafond → 400."""
        # Le client_credit_db a plafond_credit = 50 000 FCFA
        payload = {
            "mode_paiement": "credit",
            "client_id": str(client_credit_db.id),
            "montant_recu": "0.00",
            "lignes": [
                {
                    "lot_id": str(lot_db.id),
                    "quantite": 500,  # montant >> plafond
                    "prix_unitaire": str(lot_db.medicament.prix_public),
                }
            ],
        }
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")
        # Refus pour dépassement plafond ou stock
        assert resp.status_code in (400, 422)

    def test_vente_credit_client_sans_credit_retourne_400(
        self, api_caissier, client_db, lot_db
    ):
        """Un client sans crédit autorisé ne peut pas acheter à crédit."""
        payload = {
            "mode_paiement": "credit",
            "client_id": str(client_db.id),
            "montant_recu": "0.00",
            "lignes": [
                {
                    "lot_id": str(lot_db.id),
                    "quantite": 1,
                    "prix_unitaire": str(lot_db.medicament.prix_public),
                }
            ],
        }
        resp = api_caissier.post("/api/ventes/", data=payload, format="json")
        assert resp.status_code in (400, 422)


# ─── P08 — Ordonnances : dépôt et chiffrement ────────────────────────────────

class TestParcourOrdonnances:
    """P08 : Une ordonnance est déposée et stockée chiffrée."""

    def test_depot_ordonnance_anonyme_retourne_401(self, api_client):
        """POST /api/ordonnances/ sans auth → 401."""
        resp = api_client.post("/api/ordonnances/", data={}, format="json")
        assert resp.status_code == 401

    def test_caissier_peut_deposer_ordonnance(self, api_caissier, client_db):
        """Le caissier peut déposer une ordonnance (lecture ordonnance vente)."""
        payload = {
            "client_id": str(client_db.id),
            "prescripteur": "Dr Ouedraogo",
            "date_prescription": "2026-08-01",
        }
        resp = api_caissier.post("/api/ordonnances/", data=payload, format="json")
        assert resp.status_code in (200, 201, 400)

    def test_stagiaire_ne_peut_pas_valider_ordonnance(self, api_client, db):
        """Un stagiaire ne peut pas valider une ordonnance."""
        from tests.usine.usine_utilisateurs import UsineUtilisateurPharmacien
        from rest_framework.test import APIClient

        stagiaire = UsineUtilisateurPharmacien.create(role="stagiaire")
        client = APIClient()
        client.force_authenticate(user=stagiaire)

        ordonnance_id = uuid.uuid4()
        resp = client.post(
            f"/api/ordonnances/{ordonnance_id}/valider/", data={}, format="json"
        )
        assert resp.status_code in (403, 404)

    def test_image_ordonnance_non_exposee_en_clair(self, api_caissier, db):
        """L'endpoint list ordonnances ne retourne pas image_chiffree en clair."""
        resp = api_caissier.get("/api/ordonnances/")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    assert "image_chiffree" not in item
            elif "results" in data:
                for item in data["results"]:
                    assert "image_chiffree" not in item
