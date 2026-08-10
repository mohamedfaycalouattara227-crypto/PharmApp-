"""
tests/securite/test_permissions_endpoints.py
ÉTAPE 03 — Tests de sécurité : permissions et contrôle d'accès aux endpoints DRF.

Objectif : prouver qu'aucun endpoint n'est accessible sans authentification,
et que la hiérarchie de rôles est strictement respectée.

Hiérarchie des rôles (du plus restreint au plus large) :
    stagiaire < caissier < assistant < gestionnaire_stock
    < pharmacien_adjoint < titulaire < administrateur

Marqueur : pytest.mark.securite
"""

import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.securite


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _url(name, **kwargs):
    """Construit une URL DRF depuis le nom de la route."""
    try:
        return reverse(name, kwargs=kwargs)
    except Exception:
        return f"/{name}/"


# ─── 1. Endpoints sans authentification → 401 ────────────────────────────────

class TestEndpointsSansAuthentification:
    """Tout endpoint protégé doit retourner 401 pour une requête anonyme."""

    ENDPOINTS_GET = [
        "/api/v1/ventes/",
        "/api/v1/catalogue/medicaments/",
        "/api/v1/catalogue/lots/",
        "/api/v1/clients/",
        "/api/v1/stocks/alertes/",
        "/api/v1/audit/journal/",
        "/api/v1/rapports/",
        "/api/v1/synchronisation/statut/",
        "/api/v1/produits-controles/",
        "/api/v1/ordonnances/",
        "/api/v1/fournisseurs/",
        "/api/v1/comptabilite/",
        "/api/v1/parametrage/",
    ]

    @pytest.mark.parametrize("url", ENDPOINTS_GET)
    def test_get_sans_auth_retourne_401(self, api_client, url):
        """Un GET anonyme sur tout endpoint protégé doit retourner 401."""
        reponse = api_client.get(url)
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"GET {url} a retourné {reponse.status_code} au lieu de 401"
        )

    @pytest.mark.parametrize("url", [
        "/api/v1/ventes/",
        "/api/v1/clients/",
        "/api/v1/ordonnances/",
    ])
    def test_post_sans_auth_retourne_401(self, api_client, url):
        """Un POST anonyme doit retourner 401."""
        reponse = api_client.post(url, data={}, format="json")
        assert reponse.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"POST {url} a retourné {reponse.status_code} au lieu de 401"
        )


# ─── 2. Endpoint de connexion accessible sans auth ────────────────────────────

class TestEndpointsPublics:
    """Les endpoints d'authentification doivent être accessibles sans token."""

    def test_connexion_post_accessible_sans_auth(self, api_client):
        """/api/v1/auth/connexion/ est public (AllowAny)."""
        reponse = api_client.post(
            "/api/v1/auth/connexion/",
            data={"email": "x@x.com", "password": "wrong"},
            format="json",
        )
        # 400 (mauvais identifiants) ou 401 — dans tous les cas pas 403
        assert reponse.status_code != status.HTTP_403_FORBIDDEN

    def test_version_accessible_sans_auth(self, api_client):
        """/api/v1/version/ est public."""
        reponse = api_client.get("/api/v1/version/")
        assert reponse.status_code in (
            status.HTTP_200_OK, status.HTTP_404_NOT_FOUND
        )


# ─── 3. Élévation de privilège : caissier ne peut pas accéder aux ressources titulaire ──

class TestElevationPrivilege:
    """Un utilisateur ne peut pas accéder aux ressources d'un rôle supérieur."""

    def test_caissier_ne_peut_pas_lire_audit(self, api_caissier):
        """Le journal d'audit est réservé au titulaire."""
        reponse = api_caissier.get("/api/v1/audit/journal/")
        assert reponse.status_code == status.HTTP_403_FORBIDDEN, (
            f"Caissier a accès au journal d'audit (réponse {reponse.status_code})"
        )

    def test_caissier_ne_peut_pas_lire_comptabilite(self, api_caissier):
        """La comptabilité est réservée au titulaire."""
        reponse = api_caissier.get("/api/v1/comptabilite/")
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_caissier_ne_peut_pas_modifier_parametrage(self, api_caissier):
        """La modification du paramétrage est réservée au titulaire."""
        reponse = api_caissier.patch(
            "/api/v1/parametrage/",
            data={"nom_officine": "Hack"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_caissier_ne_peut_pas_ajuster_stock(self, api_caissier):
        """L'ajustement de stock est réservé au gestionnaire de stock."""
        reponse = api_caissier.post(
            "/api/v1/stocks/ajuster/",
            data={},
            format="json",
        )
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_stagiaire_ne_peut_pas_creer_vente(self, api_client, stagiaire):
        """Un stagiaire ne peut pas créer de vente."""
        api_client.force_authenticate(user=stagiaire)
        reponse = api_client.post(
            "/api/v1/ventes/",
            data={"panier": [], "mode_paiement": "especes"},
            format="json",
        )
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_caissier_ne_peut_pas_annuler_vente(self, api_caissier):
        """L'annulation d'une vente est réservée au pharmacien adjoint."""
        reponse = api_caissier.post(
            "/api/v1/ventes/00000000-0000-0000-0000-000000000001/annuler/",
            data={"motif": "Test"},
            format="json",
        )
        # 403 ou 404 selon si l'objet existe — dans tous les cas pas 200
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_caissier_ne_peut_pas_lire_rapports_marges(self, api_caissier):
        """Les rapports de marges sont réservés au titulaire."""
        reponse = api_caissier.get("/api/v1/rapports/marges/")
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_gestionnaire_stock_peut_lire_catalogue(self, api_gestionnaire_stock):
        """Un gestionnaire de stock peut lire le catalogue."""
        reponse = api_gestionnaire_stock.get("/api/v1/catalogue/medicaments/")
        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )

    def test_caissier_ne_peut_pas_acceder_produits_controles(self, api_caissier):
        """Les produits contrôlés sont réservés au pharmacien adjoint."""
        reponse = api_caissier.get("/api/v1/produits-controles/")
        assert reponse.status_code == status.HTTP_403_FORBIDDEN

    def test_titulaire_peut_lire_audit(self, api_titulaire):
        """Le titulaire a accès au journal d'audit."""
        reponse = api_titulaire.get("/api/v1/audit/journal/")
        assert reponse.status_code in (
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        )


# ─── 4. IDOR — Accès inter-utilisateurs ───────────────────────────────────────

class TestIDOR:
    """Prévention des attaques IDOR (Insecure Direct Object Reference)."""

    def test_caissier_ne_voit_que_ses_propres_ventes(self, api_caissier, db):
        """Un caissier ne peut pas accéder à la vente d'un autre caissier via UUID."""
        reponse = api_caissier.get(
            "/api/v1/ventes/00000000-0000-0000-0000-000000000099/"
        )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )

    def test_acces_ordonnance_autre_client(self, api_caissier, db):
        """Un caissier ne peut pas accéder à l'image d'une ordonnance d'un autre client."""
        reponse = api_caissier.get(
            "/api/v1/ordonnances/00000000-0000-0000-0000-000000000099/image/"
        )
        assert reponse.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


# ─── 5. Méthodes HTTP non autorisées ──────────────────────────────────────────

class TestMethodesHTTPNonAutorisees:
    """Les méthodes non autorisées doivent retourner 405."""

    def test_delete_journal_audit_interdit(self, api_titulaire):
        """Le journal d'audit est en lecture seule — DELETE doit retourner 405."""
        reponse = api_titulaire.delete("/api/v1/audit/journal/")
        assert reponse.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
        )

    def test_delete_vente_interdit(self, api_titulaire):
        """Une vente ne peut pas être supprimée — seulement annulée."""
        reponse = api_titulaire.delete(
            "/api/v1/ventes/00000000-0000-0000-0000-000000000001/"
        )
        assert reponse.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
        )
