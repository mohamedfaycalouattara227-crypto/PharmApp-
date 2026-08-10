"""
tests/unitaires/test_service_ordonnance.py
Tests unitaires du chiffrement AES-256-GCM des ordonnances et de la validation
des images uploadées.
Couverture cible : gestion/ordonnances/services.py ≥ 95 %
"""

import base64
import os
import struct

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gestion.ordonnances.services import (
    ServiceChiffrementOrdonnance,
    OrdonnanceChiffrementInvalide,
    OrdonnanceTailleExcessive,
    OrdonnanceTypeInvalide,
    valider_image_ordonnance,
)

pytestmark = pytest.mark.unitaire

# ─── Clé de test stable ──────────────────────────────────────────────────────

CLE_TEST = os.urandom(32)

# Magic bytes de test
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 500
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 500
PDF_HEADER = b"%PDF-1.4\n" + b"\x00" * 500
WEBP_HEADER = b"RIFF\x20\x00\x00\x00WEBP" + b"\x00" * 200


class TestServiceChiffrementOrdonnance:
    """Tests du cycle chiffrement/déchiffrement AES-256-GCM."""

    @pytest.fixture
    def service(self):
        return ServiceChiffrementOrdonnance(cle=CLE_TEST)

    def test_cycle_chiffrement_dechiffrement(self, service):
        """Chiffrer puis déchiffrer retourne les données d'origine."""
        donnees = b"Image ordonnance confidentielle"
        nonce, chiffre = service.chiffrer(donnees)
        assert service.dechiffrer(nonce, chiffre) == donnees

    def test_nonce_unique_par_chiffrement(self, service):
        """Deux chiffrements du même contenu produisent des nonces différents."""
        d = b"meme contenu"
        nonce1, _ = service.chiffrer(d)
        nonce2, _ = service.chiffrer(d)
        assert nonce1 != nonce2

    def test_nonce_fait_12_octets(self, service):
        """Le nonce GCM est toujours de 12 octets (standard)."""
        nonce, _ = service.chiffrer(b"test")
        assert len(nonce) == 12

    def test_chiffre_different_du_clair(self, service):
        """Le texte chiffré ne contient pas le clair en clair."""
        clair = b"donnee secrete"
        _, chiffre = service.chiffrer(clair)
        assert clair not in chiffre

    def test_tampering_detecte(self, service):
        """Altérer un octet du chiffré lève OrdonnanceChiffrementInvalide."""
        nonce, chiffre = service.chiffrer(b"donnee integre")
        chiffre_altere = bytearray(chiffre)
        chiffre_altere[0] ^= 0xFF
        with pytest.raises(OrdonnanceChiffrementInvalide):
            service.dechiffrer(nonce, bytes(chiffre_altere))

    def test_mauvais_nonce_detecte(self, service):
        """Un nonce incorrect lève OrdonnanceChiffrementInvalide."""
        nonce, chiffre = service.chiffrer(b"donnee")
        mauvais_nonce = os.urandom(12)
        with pytest.raises(OrdonnanceChiffrementInvalide):
            service.dechiffrer(mauvais_nonce, chiffre)

    def test_aad_correct_dechiffre(self, service):
        """Avec AAD, déchiffrement réussit si AAD identique."""
        aad = b"ordonnance-id-1234"
        nonce, chiffre = service.chiffrer(b"confidentiel", associe=aad)
        result = service.dechiffrer(nonce, chiffre, associe=aad)
        assert result == b"confidentiel"

    def test_aad_incorrect_echoue(self, service):
        """AAD différent à l'étape de déchiffrement → OrdonnanceChiffrementInvalide."""
        aad_chiffrement = b"ordonnance-id-1234"
        aad_dechiffrement = b"ordonnance-id-9999"
        nonce, chiffre = service.chiffrer(b"confidentiel", associe=aad_chiffrement)
        with pytest.raises(OrdonnanceChiffrementInvalide):
            service.dechiffrer(nonce, chiffre, associe=aad_dechiffrement)

    def test_chiffrement_type_invalide(self, service):
        """Passer un type non-bytes lève TypeError."""
        with pytest.raises(TypeError):
            service.chiffrer("chaine pas bytes")  # type: ignore

    def test_chiffrement_grand_fichier(self, service):
        """Fichier de 4 Mo se chiffre et déchiffre correctement."""
        grand = os.urandom(4 * 1024 * 1024)
        nonce, chiffre = service.chiffrer(grand)
        assert service.dechiffrer(nonce, chiffre) == grand


class TestValiderImageOrdonnance:
    """Tests de la validation MIME + taille des images uploadées."""

    def test_jpeg_valide(self):
        """Un JPEG correct est accepté, type réel retourné."""
        t = valider_image_ordonnance(JPEG_HEADER, "image/jpeg")
        assert t == "image/jpeg"

    def test_png_valide(self):
        t = valider_image_ordonnance(PNG_HEADER, "image/png")
        assert t == "image/png"

    def test_pdf_valide(self):
        t = valider_image_ordonnance(PDF_HEADER, "application/pdf")
        assert t == "application/pdf"

    def test_webp_valide(self):
        t = valider_image_ordonnance(WEBP_HEADER, "image/webp")
        assert t == "image/webp"

    def test_type_mime_inconnu_rejete(self):
        """Contenu non reconnu (données aléatoires) est rejeté."""
        with pytest.raises(OrdonnanceTypeInvalide):
            valider_image_ordonnance(b"\x00\x01\x02" * 100, "image/jpeg")

    def test_mime_declare_incoherent_rejete(self):
        """Un JPEG déclaré PNG est refusé."""
        with pytest.raises(OrdonnanceTypeInvalide):
            valider_image_ordonnance(JPEG_HEADER, "image/png")

    def test_fichier_vide_rejete(self):
        """Fichier vide → OrdonnanceTypeInvalide."""
        with pytest.raises(OrdonnanceTypeInvalide):
            valider_image_ordonnance(b"", "image/jpeg")

    def test_fichier_trop_grand_rejete(self, settings):
        """Fichier dépassant ORDONNANCE_MAX_SIZE_MB → OrdonnanceTailleExcessive."""
        settings.ORDONNANCE_MAX_SIZE_MB = 1
        contenu_trop_grand = JPEG_HEADER + b"\x00" * (2 * 1024 * 1024)
        with pytest.raises(OrdonnanceTailleExcessive):
            valider_image_ordonnance(contenu_trop_grand, "image/jpeg")

    def test_type_declare_vide_accepte(self):
        """Si type_mime_declare est vide, le type réel est utilisé sans erreur."""
        t = valider_image_ordonnance(PNG_HEADER, "")
        assert t == "image/png"
