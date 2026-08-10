"""
tests/integration/test_api_audit_complet.py
Tests d'intégration exhaustifs du journal d'audit (VueJournalAudit).

Branches couvertes :
  - GET /api/audit/                : liste paginée, accès réservé titulaire
  - GET /api/audit/?type_action=   : filtre par type d'action
  - GET /api/audit/?severite=      : filtre par sévérité
  - GET /api/audit/?utilisateur_id=: filtre par utilisateur
  - GET /api/audit/<id>/           : détail d'une entrée
  - Immuabilité : PUT/PATCH/DELETE refusés (405)
  - Intégrité SHA-256 : empreinte présente dans la réponse
  - Accès refusé : caissier, adjoint, non authentifié → 403 / 401
"""

import uuid
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.usine.usine_utilisateurs import (
    UsineCaissier,
    UsinePharmacienAdjoint,
    UsineTitulaire,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


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
def api_caissier(client_api, caissier):
    client_api.force_authenticate(user=caissier)
    return client_api


@pytest.fixture
def api_adjoint(client_api, adjoint):
    client_api.force_authenticate(user=adjoint)
    return client_api


@pytest.fixture
def api_titulaire(client_api, titulaire):
    client_api.force_authenticate(user=titulaire)
    return client_api


def _creer_entree_audit(
    type_action: str = "connexion_reussie",
    severite: str = "info",
    description: str = "Test audit",
    utilisateur=None,
):
    """Crée directement une entrée de journal via le manager Django."""
    from gestion.audit.models import JournalAudit
    return JournalAudit.objects.journaliser(
        type_action=type_action,
        description=description,
        severite=severite,
        utilisateur=utilisateur,
    )


# ─── Tests Accès ──────────────────────────────────────────────────────────────


class TestAccesJournalAudit:
    """Contrôle strict des permissions : seul le titulaire peut lire."""

    def test_titulaire_peut_lister(self, api_titulaire):
        rep = api_titulaire.get("/api/audit/")
        assert rep.status_code == status.HTTP_200_OK

    def test_caissier_bloque_403(self, api_caissier):
        rep = api_caissier.get("/api/audit/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_adjoint_bloque_403(self, api_adjoint):
        rep = api_adjoint.get("/api/audit/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_non_authentifie_401(self, client_api):
        rep = client_api.get("/api/audit/")
        assert rep.status_code == status.HTTP_401_UNAUTHORIZED

    def test_detail_accessible_au_titulaire(self, api_titulaire, db):
        entree = _creer_entree_audit()
        rep = api_titulaire.get(f"/api/audit/{entree.id}/")
        assert rep.status_code == status.HTTP_200_OK

    def test_detail_refuse_au_caissier(self, api_caissier, db):
        entree = _creer_entree_audit()
        rep = api_caissier.get(f"/api/audit/{entree.id}/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN

    def test_detail_refuse_a_ladjoint(self, api_adjoint, db):
        entree = _creer_entree_audit()
        rep = api_adjoint.get(f"/api/audit/{entree.id}/")
        assert rep.status_code == status.HTTP_403_FORBIDDEN


# ─── Tests Liste et Pagination ────────────────────────────────────────────────


class TestListeJournalAudit:
    """GET /api/audit/ — résultats, pagination, tri."""

    def test_liste_vide_retourne_count_zero(self, api_titulaire, db):
        rep = api_titulaire.get("/api/audit/")
        assert rep.status_code == status.HTTP_200_OK
        assert rep.json()["count"] == 0

    def test_liste_retourne_une_entree(self, api_titulaire, db):
        _creer_entree_audit()
        rep = api_titulaire.get("/api/audit/")
        assert rep.json()["count"] == 1

    def test_liste_retourne_plusieurs_entrees(self, api_titulaire, db):
        for _ in range(3):
            _creer_entree_audit()
        rep = api_titulaire.get("/api/audit/")
        assert rep.json()["count"] == 3

    def test_tri_par_date_decroissante(self, api_titulaire, db):
        """Les entrées doivent être ordonnées de la plus récente à la plus ancienne."""
        for i in range(3):
            _creer_entree_audit(description=f"Action {i}")
        rep = api_titulaire.get("/api/audit/")
        resultats = rep.json()["results"]
        dates = [r["cree_le"] for r in resultats]
        assert dates == sorted(dates, reverse=True)

    def test_pagination_presente(self, api_titulaire, db):
        rep = api_titulaire.get("/api/audit/")
        data = rep.json()
        assert "count" in data
        assert "results" in data
        assert "next" in data or data["count"] == 0


# ─── Tests Filtres ────────────────────────────────────────────────────────────


class TestFiltresJournalAudit:
    """Filtres query string : type_action, severite, utilisateur_id."""

    def test_filtre_type_action_connexion(self, api_titulaire, db):
        _creer_entree_audit(type_action="connexion_reussie")
        _creer_entree_audit(type_action="vente_creee")
        rep = api_titulaire.get("/api/audit/?type_action=connexion_reussie")
        assert rep.status_code == status.HTTP_200_OK
        types = [r["type_action"] for r in rep.json()["results"]]
        assert all(t == "connexion_reussie" for t in types)

    def test_filtre_type_action_vente(self, api_titulaire, db):
        _creer_entree_audit(type_action="vente_creee")
        _creer_entree_audit(type_action="connexion_reussie")
        rep = api_titulaire.get("/api/audit/?type_action=vente_creee")
        types = [r["type_action"] for r in rep.json()["results"]]
        assert all(t == "vente_creee" for t in types)

    def test_filtre_severite_info(self, api_titulaire, db):
        _creer_entree_audit(severite="info")
        _creer_entree_audit(severite="critique")
        rep = api_titulaire.get("/api/audit/?severite=info")
        severites = [r["severite"] for r in rep.json()["results"]]
        assert all(s == "info" for s in severites)

    def test_filtre_severite_critique(self, api_titulaire, db):
        _creer_entree_audit(severite="critique")
        _creer_entree_audit(severite="info")
        rep = api_titulaire.get("/api/audit/?severite=critique")
        severites = [r["severite"] for r in rep.json()["results"]]
        assert all(s == "critique" for s in severites)

    def test_filtre_utilisateur_id(self, api_titulaire, titulaire, db):
        _creer_entree_audit(utilisateur=titulaire)
        _creer_entree_audit(utilisateur=None)
        rep = api_titulaire.get(f"/api/audit/?utilisateur_id={titulaire.id}")
        assert rep.status_code == status.HTTP_200_OK
        resultats = rep.json()["results"]
        assert len(resultats) >= 1
        ids_utilisateurs = [r["utilisateur"] for r in resultats if r.get("utilisateur")]
        assert all(str(u) == str(titulaire.id) for u in ids_utilisateurs)

    def test_filtre_type_inconnu_retourne_zero(self, api_titulaire, db):
        _creer_entree_audit()
        rep = api_titulaire.get("/api/audit/?type_action=action_inexistante_xyz")
        assert rep.json()["count"] == 0

    def test_combinaison_type_et_severite(self, api_titulaire, db):
        _creer_entree_audit(type_action="connexion_reussie", severite="info")
        _creer_entree_audit(type_action="connexion_reussie", severite="critique")
        _creer_entree_audit(type_action="vente_creee", severite="info")
        rep = api_titulaire.get(
            "/api/audit/?type_action=connexion_reussie&severite=info"
        )
        resultats = rep.json()["results"]
        assert all(
            r["type_action"] == "connexion_reussie" and r["severite"] == "info"
            for r in resultats
        )


# ─── Tests Détail ─────────────────────────────────────────────────────────────


class TestDetailJournalAudit:
    """GET /api/audit/<id>/ — champs et intégrité."""

    def test_detail_retourne_tous_les_champs_essentiels(self, api_titulaire, db):
        entree = _creer_entree_audit(type_action="vente_creee", severite="info")
        rep = api_titulaire.get(f"/api/audit/{entree.id}/")
        data = rep.json()
        assert "id" in data
        assert "type_action" in data
        assert "description" in data
        assert "severite" in data
        assert "cree_le" in data

    def test_detail_empreinte_sha256_presente(self, api_titulaire, db):
        """L'empreinte d'intégrité SHA-256 doit être renvoyée dans la réponse."""
        entree = _creer_entree_audit()
        rep = api_titulaire.get(f"/api/audit/{entree.id}/")
        data = rep.json()
        # Le champ peut s'appeler empreinte_sha256 ou hash ou signature selon l'impl.
        champ_hash = (
            data.get("empreinte_sha256")
            or data.get("hash")
            or data.get("signature")
            or data.get("empreinte")
        )
        assert champ_hash is not None
        assert len(champ_hash) == 64  # SHA-256 hex = 64 chars

    def test_detail_id_inexistant_retourne_404(self, api_titulaire):
        rep = api_titulaire.get(f"/api/audit/{uuid.uuid4()}/")
        assert rep.status_code == status.HTTP_404_NOT_FOUND

    def test_description_correcte(self, api_titulaire, db):
        desc = "Connexion réussie pour test audit"
        entree = _creer_entree_audit(description=desc)
        rep = api_titulaire.get(f"/api/audit/{entree.id}/")
        assert rep.json()["description"] == desc


# ─── Tests Immuabilité ────────────────────────────────────────────────────────


class TestImmuabiliteJournalAudit:
    """
    Le journal d'audit est en lecture seule (ReadOnlyModelViewSet).
    PUT, PATCH et DELETE doivent retourner 405 Method Not Allowed.
    """

    def test_put_refuse_405(self, api_titulaire, db):
        entree = _creer_entree_audit()
        rep = api_titulaire.put(
            f"/api/audit/{entree.id}/",
            data={"description": "Tentative de modification"},
            format="json",
        )
        assert rep.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_refuse_405(self, api_titulaire, db):
        entree = _creer_entree_audit()
        rep = api_titulaire.patch(
            f"/api/audit/{entree.id}/",
            data={"severite": "critique"},
            format="json",
        )
        assert rep.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_refuse_405(self, api_titulaire, db):
        entree = _creer_entree_audit()
        rep = api_titulaire.delete(f"/api/audit/{entree.id}/")
        assert rep.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_post_creation_directe_refuse_405(self, api_titulaire):
        """On ne peut pas créer d'entrée d'audit via l'API REST."""
        rep = api_titulaire.post(
            "/api/audit/",
            data={"type_action": "connexion_reussie", "description": "Test"},
            format="json",
        )
        assert rep.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ─── Tests Intégrité SHA-256 ─────────────────────────────────────────────────


class TestIntegriteAudit:
    """Vérification que le calcul SHA-256 est stable et cohérent."""

    def test_empreinte_non_nulle(self, db):
        entree = _creer_entree_audit()
        assert entree.empreinte_sha256 is not None
        assert len(entree.empreinte_sha256) == 64

    def test_deux_entrees_ont_empreintes_differentes(self, db):
        e1 = _creer_entree_audit(description="Action 1")
        e2 = _creer_entree_audit(description="Action 2")
        assert e1.empreinte_sha256 != e2.empreinte_sha256

    def test_empreinte_reproductible(self, db):
        """L'empreinte d'une même entrée est toujours identique."""
        from gestion.audit.models import JournalAudit
        entree = _creer_entree_audit()
        recharge = JournalAudit.objects.get(pk=entree.pk)
        assert recharge.empreinte_sha256 == entree.empreinte_sha256

    def test_manager_journaliser_retourne_instance(self, db):
        entree = _creer_entree_audit(
            type_action="vente_creee",
            severite="avertissement",
            description="Vente créée en test",
        )
        from gestion.audit.models import JournalAudit
        assert isinstance(entree, JournalAudit)

    def test_types_actions_valides(self, db):
        from gestion.audit.models import TypeAction
        for type_action in [
            TypeAction.CONNEXION_REUSSIE,
            TypeAction.VENTE_CREEE,
            TypeAction.AJUSTEMENT_STOCK,
            TypeAction.CLOTURE_CAISSE,
            TypeAction.EXPORT_DONNEES,
        ]:
            entree = _creer_entree_audit(type_action=type_action)
            assert entree.type_action == type_action

    def test_severites_valides(self, db):
        from gestion.audit.models import Severite
        for sev in [
            Severite.INFO,
            Severite.AVERTISSEMENT,
            Severite.ALERTE,
            Severite.CRITIQUE,
        ]:
            entree = _creer_entree_audit(severite=sev)
            assert entree.severite == sev
