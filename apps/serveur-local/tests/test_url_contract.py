"""
Test de contrat d'URL (DT-003, corrigé à l'étape 00).

`pharmapp/urls.py` inclut `api.urls` sous le préfixe "api/". Si `api/urls.py`
re-préfixe ses propres routes par "api/", les URL effectives deviennent
"/api/api/...", ce qui casse silencieusement tout le poste client (qui
appelle "/api/...", cf. `api-client.ts`). Ce test verrouille le contrat pour
qu'une régression de ce type fasse échouer la CI plutôt que d'être découverte
en officine.
"""

from django.urls import get_resolver
from django.test import Client
import pytest


def _toutes_les_urls_effectives() -> list[str]:
    resolver = get_resolver()
    return [str(p.pattern) for p in resolver.url_patterns]


def test_aucune_route_nest_doublement_prefixee_api():
    urls = "\n".join(_toutes_les_urls_effectives())
    assert "api/api/" not in urls, (
        "Préfixe /api/api/ détecté : api/urls.py re-préfixe des routes déjà "
        "incluses sous 'api/' par pharmapp/urls.py (régression DT-003)."
    )


@pytest.mark.django_db
def test_endpoint_medicaments_repond_sur_prefixe_simple(client: Client):
    # Le routeur DRF enregistre "medicaments" ; l'URL effective doit être
    # "/api/medicaments/", jamais "/api/api/medicaments/".
    reponse = client.get("/api/medicaments/")
    assert reponse.status_code in (200, 401, 403), (
        f"Statut inattendu {reponse.status_code} : la route /api/medicaments/ "
        "ne répond pas comme attendu (vérifier le préfixage)."
    )


@pytest.mark.django_db
def test_double_prefixe_est_bien_absent(client: Client):
    reponse = client.get("/api/api/medicaments/")
    assert reponse.status_code == 404
