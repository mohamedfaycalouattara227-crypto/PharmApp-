"""
Tests de l'endpoint d'identité de build (ÉTAPE 00, critère de sortie n°1).

Ces tests verrouillent le contrat : si quelqu'un supprime la route, renomme un
champ ou ré-introduit une version codée en dur, la CI casse.
"""

from pathlib import Path

import pytest
from django.urls import reverse

from pharmapp.version import version_applicative


def _racine_depot() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "VERSION").is_file():
            return parent
    raise AssertionError("Fichier VERSION introuvable : le dépôt n'est pas unifié.")


@pytest.mark.django_db
def test_endpoint_version_accessible_sans_authentification(client):
    reponse = client.get("/api/v1/version/")
    assert reponse.status_code == 200
    corps = reponse.json()
    for champ in ("application", "version", "revision", "construit_le", "environnement", "api"):
        assert champ in corps, f"champ manquant dans /api/v1/version/ : {champ}"
    assert corps["application"] == "pharmapp-serveur-local"
    assert corps["api"] == "v1"


@pytest.mark.django_db
def test_version_exposee_identique_au_fichier_VERSION(client):
    attendue = (_racine_depot() / "VERSION").read_text(encoding="utf-8").strip()
    assert version_applicative() == attendue
    assert client.get("/api/v1/version/").json()["version"] == attendue


def test_version_est_semantique():
    import re

    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version_applicative()), (
        "La version doit respecter le versionnement sémantique (MAJEUR.MINEUR.CORRECTIF)."
    )


def test_url_nommee_disponible():
    assert reverse("version") == "/api/v1/version/"
