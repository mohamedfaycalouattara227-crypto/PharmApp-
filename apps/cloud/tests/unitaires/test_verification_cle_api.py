"""
tests/unitaires/test_verification_cle_api.py
Tests unitaires — vérification de clés API (anti-timing, cas limites).

Aucune base de données requise.
"""

import pytest
from apps.identite.services import generer_cle_api, verifier_cle_api, _hacher_cle


@pytest.mark.unitaire
class TestVerificationCleApi:

    def test_cle_valide_acceptee(self):
        """Une clé valide doit être acceptée."""
        cle, _, hash_sha256 = generer_cle_api()
        assert verifier_cle_api(cle, hash_sha256) is True

    def test_cle_incorrecte_rejetee(self):
        """Une clé incorrecte doit être rejetée."""
        _, _, hash_sha256 = generer_cle_api()
        assert verifier_cle_api("phk_mauvaise_cle", hash_sha256) is False

    def test_hash_incorrect_rejete(self):
        """Un hash ne correspondant pas à la clé doit être rejeté."""
        cle, _, _ = generer_cle_api()
        _, _, autre_hash = generer_cle_api()
        assert verifier_cle_api(cle, autre_hash) is False

    def test_cle_vide_rejetee(self):
        """Une clé vide doit être rejetée sans exception."""
        _, _, hash_sha256 = generer_cle_api()
        assert verifier_cle_api("", hash_sha256) is False

    def test_hash_vide_rejete(self):
        """Un hash vide doit être rejeté sans exception."""
        cle, _, _ = generer_cle_api()
        assert verifier_cle_api(cle, "") is False

    def test_deux_vides_rejetes(self):
        """Deux valeurs vides doivent être rejetées."""
        assert verifier_cle_api("", "") is False

    def test_cle_tronquee_rejetee(self):
        """Une clé tronquée doit être rejetée."""
        cle, _, hash_sha256 = generer_cle_api()
        assert verifier_cle_api(cle[:-5], hash_sha256) is False

    def test_cle_avec_caractere_supplementaire_rejetee(self):
        """Une clé avec un caractère supplémentaire doit être rejetée."""
        cle, _, hash_sha256 = generer_cle_api()
        assert verifier_cle_api(cle + "X", hash_sha256) is False

    def test_hacher_cle_deterministe(self):
        """Le même input doit toujours produire le même hash."""
        cle = "phk_test_constant_input_12345"
        hash1 = _hacher_cle(cle)
        hash2 = _hacher_cle(cle)
        assert hash1 == hash2

    def test_hacher_cle_sensible_casse(self):
        """Le hash doit être sensible à la casse."""
        hash_min = _hacher_cle("phk_abcdef")
        hash_maj = _hacher_cle("phk_ABCDEF")
        assert hash_min != hash_maj
