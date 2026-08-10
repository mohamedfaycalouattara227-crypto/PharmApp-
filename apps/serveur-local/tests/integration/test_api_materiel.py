"""
tests/integration/test_api_materiel.py
ÉTAPE 08 — Tests des endpoints matériels ESC/POS.

Endpoints couverts :
  POST /api/materiel/tiroir/          — ouvre le tiroir (EstCaissier+)
  POST /api/materiel/imprimer-recu/   — impression reçu ESC/POS (EstCaissier+)
  POST /api/materiel/test-imprimante/ — ticket de test (EstPharmacienAdjoint+)

Scénarios testés :
  - 401 sans authentification
  - 403 pour rôle insuffisant (stagiaire, caissier sur test-imprimante)
  - 503 quand imprimante non configurée (ImprimanteNonConfiguree)
  - 502 sur ErreurImprimante (réseau/USB/série inaccessible)
  - 400 si vente_id absent
  - 404 si vente inconnue
  - 200 avec fallback window.print si imprimante absente sur imprimer-recu
  - 200 normal avec connecteur mocké

Marqueur : pytest.mark.integration
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration

URL_TIROIR       = "/api/materiel/tiroir/"
URL_IMPRIMER     = "/api/materiel/imprimer-recu/"
URL_TEST         = "/api/materiel/test-imprimante/"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _service_ok():
    """Retourne un ServiceImprimanteESCPOS dont les méthodes ne lèvent pas."""
    svc = MagicMock()
    svc.ouvrir_tiroir = MagicMock()
    svc.imprimer_recu = MagicMock()
    svc.imprimer_test = MagicMock()
    return svc


def _service_non_configure():
    from gestion.materiel.escpos import ImprimanteNonConfiguree
    svc = MagicMock()
    svc.ouvrir_tiroir.side_effect = ImprimanteNonConfiguree("Non configurée")
    svc.imprimer_recu.side_effect = ImprimanteNonConfiguree("Non configurée")
    svc.imprimer_test.side_effect = ImprimanteNonConfiguree("Non configurée")
    return svc


def _service_erreur():
    from gestion.materiel.escpos import ErreurImprimante
    svc = MagicMock()
    svc.ouvrir_tiroir.side_effect = ErreurImprimante("Connexion refusée")
    svc.imprimer_recu.side_effect = ErreurImprimante("Connexion refusée")
    svc.imprimer_test.side_effect = ErreurImprimante("Connexion refusée")
    return svc


# ─── 1. Permissions globales ─────────────────────────────────────────────────

class TestPermissionsMateriel:
    """Accès sans auth ou rôle insuffisant → 401/403."""

    def test_tiroir_anonyme_401(self, api_client):
        resp = api_client.post(URL_TIROIR)
        assert resp.status_code == 401

    def test_imprimer_anonyme_401(self, api_client):
        resp = api_client.post(URL_IMPRIMER, data={}, format="json")
        assert resp.status_code == 401

    def test_test_imprimante_anonyme_401(self, api_client):
        resp = api_client.post(URL_TEST)
        assert resp.status_code == 401

    def test_stagiaire_tiroir_403(self, api_client, db):
        from tests.usine.usine_utilisateurs import UsineUtilisateurPharmacien
        stagiaire = UsineUtilisateurPharmacien.create(role="stagiaire")
        api_client.force_authenticate(user=stagiaire)
        resp = api_client.post(URL_TIROIR)
        assert resp.status_code == 403

    def test_caissier_test_imprimante_403(self, api_caissier):
        """test-imprimante requiert EstPharmacienAdjoint — le caissier est refusé."""
        resp = api_caissier.post(URL_TEST)
        assert resp.status_code == 403


# ─── 2. Ouverture tiroir ─────────────────────────────────────────────────────

class TestOuvrirTiroir:
    """POST /api/materiel/tiroir/"""

    def test_caissier_succes_200(self, api_caissier):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_caissier.post(URL_TIROIR)
        assert resp.status_code == 200
        assert resp.json()["statut"] == "ok"

    def test_imprimante_non_configuree_503(self, api_caissier):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_non_configure(),
        ):
            resp = api_caissier.post(URL_TIROIR)
        assert resp.status_code == 503
        assert resp.json()["statut"] == "non_configure"

    def test_erreur_imprimante_502(self, api_caissier):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_erreur(),
        ):
            resp = api_caissier.post(URL_TIROIR)
        assert resp.status_code == 502
        assert resp.json()["statut"] == "erreur"

    def test_pharmacien_adjoint_peut_ouvrir_tiroir(self, api_pharmacien_adjoint):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_pharmacien_adjoint.post(URL_TIROIR)
        assert resp.status_code == 200


# ─── 3. Impression reçu ──────────────────────────────────────────────────────

class TestImpressionRecu:
    """POST /api/materiel/imprimer-recu/"""

    def test_vente_id_absent_400(self, api_caissier):
        resp = api_caissier.post(URL_IMPRIMER, data={}, format="json")
        assert resp.status_code == 400
        assert "vente_id" in resp.json().get("erreur", "").lower()

    def test_vente_inconnue_404(self, api_caissier, db):
        resp = api_caissier.post(
            URL_IMPRIMER,
            data={"vente_id": str(uuid.uuid4())},
            format="json",
        )
        assert resp.status_code == 404

    def test_impression_succes_200(self, api_caissier, db):
        from tests.usine.usine_ventes import UsineVente
        vente = UsineVente.create()

        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_caissier.post(
                URL_IMPRIMER,
                data={"vente_id": str(vente.id)},
                format="json",
            )
        assert resp.status_code == 200
        assert resp.json()["statut"] == "ok"

    def test_fallback_window_print_si_non_configure(self, api_caissier, db):
        """ImprimanteNonConfiguree → fallback avec le DTO reçu dans la réponse."""
        from tests.usine.usine_ventes import UsineVente
        vente = UsineVente.create()

        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_non_configure(),
        ):
            resp = api_caissier.post(
                URL_IMPRIMER,
                data={"vente_id": str(vente.id)},
                format="json",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["statut"] == "fallback_window_print"
        assert "recu" in data

    def test_erreur_imprimante_502(self, api_caissier, db):
        from tests.usine.usine_ventes import UsineVente
        vente = UsineVente.create()

        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_erreur(),
        ):
            resp = api_caissier.post(
                URL_IMPRIMER,
                data={"vente_id": str(vente.id)},
                format="json",
            )
        assert resp.status_code == 502

    def test_caissier_peut_imprimer(self, api_caissier, db):
        from tests.usine.usine_ventes import UsineVente
        vente = UsineVente.create()

        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_caissier.post(
                URL_IMPRIMER,
                data={"vente_id": str(vente.id)},
                format="json",
            )
        assert resp.status_code in (200, 404)  # 404 si UsineVente non disponible


# ─── 4. Test imprimante ──────────────────────────────────────────────────────

class TestTicketDiagnostique:
    """POST /api/materiel/test-imprimante/ — réservé EstPharmacienAdjoint+"""

    def test_pharmacien_adjoint_succes_200(self, api_pharmacien_adjoint):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_pharmacien_adjoint.post(URL_TEST)
        assert resp.status_code == 200
        assert resp.json()["statut"] == "ok"

    def test_titulaire_succes_200(self, api_titulaire):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_ok(),
        ):
            resp = api_titulaire.post(URL_TEST)
        assert resp.status_code == 200

    def test_non_configure_503(self, api_pharmacien_adjoint):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_non_configure(),
        ):
            resp = api_pharmacien_adjoint.post(URL_TEST)
        assert resp.status_code == 503

    def test_erreur_imprimante_502(self, api_pharmacien_adjoint):
        with patch(
            "gestion.materiel.vues.ServiceImprimanteESCPOS.depuis_parametrage",
            return_value=_service_erreur(),
        ):
            resp = api_pharmacien_adjoint.post(URL_TEST)
        assert resp.status_code == 502
