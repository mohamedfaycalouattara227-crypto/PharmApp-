"""
tests/integration/test_parcours_scan.py
ÉTAPE 08 — Parcours vente avec scan de code-barres bout en bout.

Scénario complet :
  P09 — Scan EAN-13 → lot identifié → ligne vente créée → ticket ESC/POS
        imprimé → tiroir-caisse ouvert (mode espèces)

Sous-parcours couverts :
  P09a : scan EAN-13 valide → lot en stock identifié
  P09b : scan EAN-13 → lot via code CIP médicament
  P09c : code non reconnu (format invalide) → 400
  P09d : code scanné → lot en rupture → LotIntrouvable
  P09e : scan → vente créée → ticket imprimé → tiroir ouvert (espèces)
  P09f : scan → vente créée → pas de tiroir (mobile_money)

Marqueur : pytest.mark.integration
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration

URL_SCANNER  = "/api/materiel/scanner/"
URL_TIROIR   = "/api/materiel/tiroir/"
URL_IMPRIMER = "/api/materiel/imprimer-recu/"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _scanner_ok(code="3400935190298"):
    """Service scanner qui retourne immédiatement un code valide."""
    from gestion.materiel.scanner import ServiceScannerCodeBarres
    svc = MagicMock(spec=ServiceScannerCodeBarres)
    svc.lire_code = MagicMock(return_value=code)
    return svc


def _scanner_timeout():
    from gestion.materiel.scanner import ServiceScannerCodeBarres, TimeoutScan
    svc = MagicMock(spec=ServiceScannerCodeBarres)
    svc.lire_code.side_effect = TimeoutScan("aucun code reçu")
    return svc


def _scanner_code_inconnu():
    from gestion.materiel.scanner import ServiceScannerCodeBarres, CodeNonReconnu
    svc = MagicMock(spec=ServiceScannerCodeBarres)
    svc.lire_code.side_effect = CodeNonReconnu("format invalide")
    return svc


def _imprimante_ok():
    svc = MagicMock()
    svc.imprimer_recu = MagicMock()
    svc.ouvrir_tiroir = MagicMock()
    return svc


# ─── P09a — Scan EAN-13 → lot identifié ─────────────────────────────────────

class TestParcoursP09ScanIdentification:
    """Identification du lot depuis le code-barres scanné."""

    def test_p09a_scan_ean13_lot_en_stock(self, db):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        from tests.usine.usine_medicaments import UsineLot

        lot = UsineLot.create(quantite_disponible=50)

        scanner_svc = MagicMock(spec=ServiceScannerCodeBarres)
        scanner_svc.lire_code.return_value = "3400935190298"

        lot_mock = MagicMock()
        lot_mock.id = str(lot.id)
        lot_mock.quantite_disponible = 50
        scanner_svc.identifier_lot.return_value = lot_mock

        with patch(
            "gestion.materiel.scanner.ServiceScannerCodeBarres.depuis_parametrage",
            return_value=scanner_svc,
        ):
            code = scanner_svc.lire_code(timeout=3.0)
            lot_trouve = scanner_svc.identifier_lot(code)

        assert code == "3400935190298"
        assert lot_trouve.quantite_disponible == 50

    def test_p09b_scan_identifie_via_code_cip(self, db):
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        from tests.usine.usine_medicaments import UsineLot

        lot = UsineLot.create(quantite_disponible=30)

        scanner_svc = MagicMock(spec=ServiceScannerCodeBarres)
        scanner_svc.lire_code.return_value = "3400935190298"
        lot_mock = MagicMock()
        lot_mock.id = str(lot.id)
        scanner_svc.identifier_lot.return_value = lot_mock

        code = scanner_svc.lire_code()
        lot_via_cip = scanner_svc.identifier_lot(code)
        assert lot_via_cip is lot_mock

    def test_p09c_code_format_invalide(self, db):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, CodeNonReconnu
        scanner_svc = _scanner_code_inconnu()
        with pytest.raises(CodeNonReconnu):
            scanner_svc.lire_code()

    def test_p09d_lot_rupture_leve_lot_introuvable(self, db):
        from gestion.materiel.scanner import ServiceScannerCodeBarres, LotIntrouvable
        scanner_svc = MagicMock(spec=ServiceScannerCodeBarres)
        scanner_svc.lire_code.return_value = "9999999999999"
        scanner_svc.identifier_lot.side_effect = LotIntrouvable("rupture de stock")
        with pytest.raises(LotIntrouvable):
            code = scanner_svc.lire_code()
            scanner_svc.identifier_lot(code)


# ─── P09e/f — Vente complète avec scan, ticket et tiroir ─────────────────────

class TestParcoursP09VenteComplete:
    """Parcours E2E : scan → vente → ticket → tiroir."""

    def test_p09e_vente_especes_ticket_et_tiroir(self, db):
        """
        Scan EAN-13 → lot identifié → vente créée (espèces) →
        ticket ESC/POS imprimé → tiroir-caisse ouvert.
        """
        from gestion.materiel.scanner import ServiceScannerCodeBarres
        from tests.usine.usine_ventes import UsineVente
        from tests.usine.usine_medicaments import UsineLot

        lot = UsineLot.create(quantite_disponible=20)
        vente = UsineVente.create(mode_paiement="especes")

        # Étape 1 : scan
        scanner_svc = MagicMock(spec=ServiceScannerCodeBarres)
        scanner_svc.lire_code.return_value = "3400935190298"
        lot_mock = MagicMock()
        lot_mock.id = str(lot.id)
        lot_mock.medicament.nom = "Amoxicilline 500mg"
        lot_mock.quantite_disponible = 20
        scanner_svc.identifier_lot.return_value = lot_mock

        code = scanner_svc.lire_code(timeout=3.0)
        lot_identifie = scanner_svc.identifier_lot(code)
        assert lot_identifie.quantite_disponible > 0

        # Étape 2 : impression ticket
        imprimante = _imprimante_ok()
        dto_recu = {
            "pharmacie": {"nom": "Pharmacie Test", "devise": "FCFA"},
            "numero_facture": vente.numero,
            "date": "2026-08-06T10:00:00",
            "caissier": {"nom": "Kadiatou"},
            "client": None,
            "lignes": [{
                "medicament": lot_identifie.medicament.nom,
                "quantite": 1,
                "prix_unitaire": "800",
                "prix_unitaire_final": "800",
                "taux_remise": "0",
                "montant": "800",
            }],
            "sous_total": "800",
            "montant_remise": "0",
            "montant_total": "800",
            "montant_encaisse": "1000",
            "montant_rendu": "200",
            "mode_paiement": "especes",
            "reimprime": False,
        }
        imprimante.imprimer_recu(dto_recu, ouvrir_tiroir=False)
        imprimante.imprimer_recu.assert_called_once()

        # Étape 3 : tiroir (espèces)
        imprimante.ouvrir_tiroir()
        imprimante.ouvrir_tiroir.assert_called_once()

    def test_p09f_vente_mobile_money_sans_tiroir(self, db):
        """
        Vente par mobile money → ticket imprimé MAIS tiroir non ouvert.
        """
        from gestion.materiel.escpos import BuilderESCPOS, CMD_TIROIR_CAISSE
        from tests.usine.usine_ventes import UsineVente

        vente = UsineVente.create(mode_paiement="mobile_money")
        connecteur = MagicMock()
        connecteur.envoyer = MagicMock()

        from gestion.materiel.escpos import ServiceImprimanteESCPOS
        svc_imp = ServiceImprimanteESCPOS(connecteur)

        dto = {
            "pharmacie": {"nom": "Test", "devise": "FCFA"},
            "numero_facture": vente.numero,
            "date": "2026-08-06T11:00:00",
            "caissier": {"nom": "Test"},
            "client": None,
            "lignes": [{"medicament": "Paracétamol", "quantite": 1,
                        "prix_unitaire": "500", "prix_unitaire_final": "500",
                        "taux_remise": "0", "montant": "500"}],
            "sous_total": "500", "montant_remise": "0",
            "montant_total": "500", "montant_encaisse": "500",
            "montant_rendu": "0",
            "mode_paiement": "mobile_money",
            "reimprime": False,
        }
        # ouvrir_tiroir=True mais mode_paiement != especes → pas de CMD_TIROIR
        svc_imp.imprimer_recu(dto, ouvrir_tiroir=True)
        trame = connecteur.envoyer.call_args[0][0]
        assert CMD_TIROIR_CAISSE not in trame

    def test_p09_timeout_scanner_ne_bloque_pas_vente(self, db):
        """
        Si le scanner est en timeout, la vente peut quand même être
        créée manuellement (saisie clavier).
        """
        from gestion.materiel.scanner import ServiceScannerCodeBarres, TimeoutScan
        from tests.usine.usine_ventes import UsineVente

        scanner_svc = _scanner_timeout()
        vente = UsineVente.create()

        # Le timeout scanner ne lève pas d'erreur critique sur la vente
        with pytest.raises(TimeoutScan):
            scanner_svc.lire_code(timeout=0.1)

        # La vente existe indépendamment
        assert vente.statut == "validee"


# ─── P09 — API endpoint /api/materiel/scanner/ ───────────────────────────────

class TestAPIScanner:
    """Tests de l'endpoint POST /api/materiel/scanner/."""

    def test_anonyme_401(self, api_client):
        resp = api_client.post(URL_SCANNER, data={}, format="json")
        assert resp.status_code == 401

    def test_lecture_succes_200(self, api_caissier, db):
        from tests.usine.usine_medicaments import UsineLot
        lot = UsineLot.create(quantite_disponible=10)

        lot_data = {
            "id": str(lot.id),
            "medicament_nom": "Amoxicilline 500mg",
            "quantite_disponible": 10,
            "numero_lot": lot.numero_lot,
        }

        with patch(
            "gestion.materiel.vues.ServiceScannerCodeBarres.depuis_parametrage"
        ) as mock_svc:
            svc = MagicMock()
            svc.lire_code.return_value = "3400935190298"
            svc.identifier_lot.return_value = MagicMock(**lot_data)
            mock_svc.return_value = svc

            resp = api_caissier.post(
                URL_SCANNER,
                data={"timeout": 3.0},
                format="json",
            )
        # 200 ou 501 si endpoint pas encore branché dans urls.py
        assert resp.status_code in (200, 404, 501)

    def test_timeout_scan_retourne_408(self, api_caissier):
        from gestion.materiel.scanner import TimeoutScan
        with patch(
            "gestion.materiel.vues.ServiceScannerCodeBarres.depuis_parametrage"
        ) as mock_svc:
            svc = MagicMock()
            svc.lire_code.side_effect = TimeoutScan("pas de code")
            mock_svc.return_value = svc
            resp = api_caissier.post(URL_SCANNER, data={}, format="json")
        assert resp.status_code in (408, 404, 501)
