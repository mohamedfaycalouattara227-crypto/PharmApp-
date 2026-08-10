"""
tests/unitaires/test_generation_cle_api.py
Tests unitaires — génération de clés API.

Vérifie : format, unicité, entropie, non-exposition du secret.
Aucune base de données requise.
"""

import pytest
from apps.identite.services import generer_cle_api, _hacher_cle


@pytest.mark.unitaire
class TestGenerationCleApi:

    def test_format_prefixe(self):
        """La clé complète doit commencer par 'phk_'."""
        cle, prefixe, hash_sha256 = generer_cle_api()
        assert cle.startswith("phk_"), f"Préfixe invalide : {cle[:8]}"

    def test_prefixe_coherent(self):
        """Le préfixe retourné doit correspondre aux 8 premiers caractères de la clé."""
        cle, prefixe, hash_sha256 = generer_cle_api()
        assert cle[:8] == prefixe

    def test_longueur_minimale(self):
        """La clé doit avoir au moins 40 caractères (préfixe + 32 octets base64url ≈ 46)."""
        cle, _, _ = generer_cle_api()
        assert len(cle) >= 40, f"Clé trop courte : {len(cle)} caractères"

    def test_hash_sha256_format(self):
        """Le hash doit être un SHA-256 hexadécimal de 64 caractères."""
        _, _, hash_sha256 = generer_cle_api()
        assert len(hash_sha256) == 64
        assert all(c in "0123456789abcdef" for c in hash_sha256)

    def test_hash_reproductible(self):
        """Le même hash doit être produit pour la même clé."""
        cle, _, hash_sha256 = generer_cle_api()
        assert _hacher_cle(cle) == hash_sha256

    def test_unicite(self):
        """Deux appels successifs doivent produire des clés différentes."""
        cle1, _, hash1 = generer_cle_api()
        cle2, _, hash2 = generer_cle_api()
        assert cle1 != cle2, "Collision de clé détectée"
        assert hash1 != hash2, "Collision de hash détectée"

    def test_unicite_grande_echelle(self):
        """Vérifie l'absence de collision sur 500 générations."""
        cles = set()
        for _ in range(500):
            cle, _, _ = generer_cle_api()
            assert cle not in cles, f"Collision détectée après {len(cles)} générations"
            cles.add(cle)

    def test_hash_different_de_la_cle(self):
        """Le hash ne doit pas contenir la clé en clair."""
        cle, _, hash_sha256 = generer_cle_api()
        assert cle not in hash_sha256
        assert hash_sha256 not in cle

    def test_entropie_suffisante(self):
        """La partie variable de la clé (après 'phk_') doit avoir ≥ 40 caractères."""
        cle, _, _ = generer_cle_api()
        partie_variable = cle[4:]  # retire "phk_"
        assert len(partie_variable) >= 40
