"""
gestion/ordonnances/services.py

Service de chiffrement AES-256-GCM des images d'ordonnances.

Modèle de menace :
    - Les images d'ordonnances contiennent des données de santé personnelles.
    - Elles NE DOIVENT PAS être stockées en clair sur disque ni synchronisées.
    - La clé maîtresse est chargée depuis `settings.ORDONNANCE_ENCRYPTION_KEY`
      (base64 urlsafe de 32 octets, ou passphrase dérivée via HKDF-SHA256).

Format du blob stocké :
    - `vecteur_initialisation` : 12 octets aléatoires par ordonnance (nonce GCM).
    - `image_chiffree`         : ciphertext || tag (16 octets tag GCM à la fin).
    - Chaque ordonnance a un nonce unique — jamais réutilisé pour la même clé.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from django.conf import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gestion.exceptions import ExceptionPharmApp

logger = logging.getLogger("pharmapp.securite")


# ─── Erreurs dédiées ─────────────────────────────────────────────────────────


class OrdonnanceChiffrementInvalide(ExceptionPharmApp):
    """L'image chiffrée est invalide, tronquée ou altérée."""
    code_erreur = "ordonnance_chiffrement_invalide"
    statut_http = 400


class OrdonnanceTailleExcessive(ExceptionPharmApp):
    """L'image dépasse la taille maximale autorisée."""
    code_erreur = "ordonnance_taille_excessive"
    statut_http = 400


class OrdonnanceTypeInvalide(ExceptionPharmApp):
    """Type MIME non autorisé pour une ordonnance."""
    code_erreur = "ordonnance_type_invalide"
    statut_http = 400


# ─── Dérivation de clé ───────────────────────────────────────────────────────


def _cle_maitresse() -> bytes:
    """
    Retourne 32 octets de clé.

    Accepte trois formats de configuration :
      * base64 urlsafe (44 caractères) → décodé
      * hexadécimal (64 caractères)     → décodé
      * chaîne arbitraire               → dérivée via SHA-256 (compat dev)
    """
    raw = settings.ORDONNANCE_ENCRYPTION_KEY
    if not raw:
        raise RuntimeError("ORDONNANCE_ENCRYPTION_KEY est vide.")

    if isinstance(raw, str):
        # base64 urlsafe strict (avec ou sans padding)
        try:
            decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
            if len(decoded) == 32:
                return decoded
        except Exception:
            # Pas un base64 urlsafe valide — on essaie les autres formats ci-dessous.
            pass
        # hexadécimal
        if len(raw) == 64:
            try:
                return bytes.fromhex(raw)
            except ValueError:
                pass
        # clé fournie telle quelle : elle DOIT faire exactement 32 octets.
        # Aucune dérivation SHA-256 de repli : une passphrase courte donnerait
        # une clé « valide » et masquerait une configuration dangereuse.
        brut = raw.encode("utf-8")
        if len(brut) == 32:
            return brut
        raise RuntimeError(
            "ORDONNANCE_ENCRYPTION_KEY invalide : 32 octets requis "
            "(base64url, hexadécimal 64 caractères, ou chaîne de 32 octets)."
        )

    if isinstance(raw, (bytes, bytearray)) and len(raw) == 32:
        return bytes(raw)

    raise RuntimeError("ORDONNANCE_ENCRYPTION_KEY invalide (32 octets requis).")


# ─── API publique ────────────────────────────────────────────────────────────


class ServiceOrdonnance:
    """Service métier pour la gestion des ordonnances."""

    def consulter_image(self, ordonnance) -> bytes:
        """Déchiffre et retourne l'image d'une ordonnance."""
        if not ordonnance.image_chiffree or not ordonnance.vecteur_initialisation:
            raise ValueError("L'ordonnance n'a pas d'image associée.")
        
        service = ServiceChiffrementOrdonnance()
        return service.dechiffrer(
            nonce=ordonnance.vecteur_initialisation,
            chiffre=ordonnance.image_chiffree,
            associe=None
        )


class ServiceChiffrementOrdonnance:
    """Encapsule AES-256-GCM pour les images d'ordonnance."""

    def __init__(self, cle: bytes | None = None) -> None:
        self._aesgcm = AESGCM(cle if cle is not None else _cle_maitresse())

    def chiffrer(self, donnees: bytes, associe: bytes | None = None) -> tuple[bytes, bytes]:
        """
        Chiffre `donnees` et retourne `(nonce, ciphertext_avec_tag)`.

        `associe` : Additional Authenticated Data — typiquement l'ID de
        l'ordonnance, lié cryptographiquement au chiffré (empêche les
        substitutions de blobs entre ordonnances).
        """
        if not isinstance(donnees, (bytes, bytearray)):
            raise TypeError("donnees doit être bytes.")
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, bytes(donnees), associe)
        return nonce, ct

    def dechiffrer(self, nonce: bytes, chiffre: bytes, associe: bytes | None = None) -> bytes:
        """Déchiffre et vérifie l'authenticité (tag GCM)."""
        try:
            return self._aesgcm.decrypt(bytes(nonce), bytes(chiffre), associe)
        except Exception as exc:
            logger.error("ordonnance_dechiffrement_echec", extra={"raison": type(exc).__name__})
            raise OrdonnanceChiffrementInvalide() from exc


# ─── API fonctionnelle (façade) ──────────────────────────────────────────────
# Ces fonctions sont l'API stable utilisée par les vues, les services et les
# tests ; elles délèguent à ServiceChiffrementOrdonnance.


def chiffrer_image_ordonnance(
    donnees: bytes, associe: bytes | None = None
) -> tuple[bytes, bytes]:
    """Chiffre une image d'ordonnance — retourne ``(nonce, ciphertext)``."""
    return ServiceChiffrementOrdonnance().chiffrer(donnees, associe)


def dechiffrer_image_ordonnance(
    nonce: bytes, chiffre: bytes, associe: bytes | None = None
) -> bytes:
    """Déchiffre une image d'ordonnance et vérifie son intégrité (tag GCM)."""
    return ServiceChiffrementOrdonnance().dechiffrer(nonce, chiffre, associe)


# ─── Validation upload ───────────────────────────────────────────────────────


# Signatures binaires (magic bytes) reconnues.
# On NE fait PAS confiance à l'en-tête Content-Type envoyé par le client :
# il est trivialement falsifiable. On sniffe le contenu réel.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)


def _sniffer_type_mime(donnees: bytes) -> str | None:
    """Détecte le type MIME réel via les magic bytes. WebP nécessite RIFF+WEBP."""
    for signature, mime in _SIGNATURES:
        if donnees.startswith(signature):
            return mime
    if len(donnees) >= 12 and donnees[:4] == b"RIFF" and donnees[8:12] == b"WEBP":
        return "image/webp"
    return None


def valider_image_ordonnance(donnees: bytes, type_mime_declare: str) -> str:
    """
    Vérifie la taille, sniffe le type MIME réel, et impose la cohérence avec
    la valeur déclarée par le client. Retourne le type MIME **réel**, qui doit
    être utilisé pour la persistance (jamais le type MIME déclaré).
    """
    max_octets = getattr(settings, "ORDONNANCE_MAX_SIZE_MB", 5) * 1024 * 1024
    if len(donnees) == 0:
        raise OrdonnanceTypeInvalide("Fichier vide.", type_mime=type_mime_declare or "", autorises=[])
    if len(donnees) > max_octets:
        raise OrdonnanceTailleExcessive(
            f"Image trop volumineuse : {len(donnees)} octets (max {max_octets}).",
            taille=len(donnees),
            maximum=max_octets,
        )

    autorises = getattr(
        settings, "ORDONNANCE_TYPES_MIME_AUTORISES",
        ("image/jpeg", "image/png", "image/webp", "application/pdf"),
    )

    type_reel = _sniffer_type_mime(donnees)
    if type_reel is None or type_reel not in autorises:
        logger.warning(
            "upload_ordonnance_rejete_mime",
            extra={"type_mime_declare": type_mime_declare, "type_mime_reel": type_reel},
        )
        raise OrdonnanceTypeInvalide(
            "Contenu binaire non reconnu ou non autorisé.",
            type_mime=type_reel or "inconnu",
            autorises=list(autorises),
        )

    # Cohérence : le client ne peut pas déclarer un type MIME différent
    # de celui déduit des magic bytes (empêche l'exfiltration de payload
    # arbitraire déguisé en image).
    if type_mime_declare and type_mime_declare.lower() != type_reel:
        logger.warning(
            "upload_ordonnance_incoherence_mime",
            extra={"type_mime_declare": type_mime_declare, "type_mime_reel": type_reel},
        )
        raise OrdonnanceTypeInvalide(
            "Type MIME déclaré incohérent avec le contenu du fichier.",
            type_mime=type_mime_declare,
            autorises=[type_reel],
        )

    return type_reel
