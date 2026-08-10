"""
gestion/parametrage/models_cloud.py
Paramètres de connexion au Cloud PharmApp — côté serveur local.

OfficineParametrage est un singleton (comme Parametrage) qui stocke :
  - L'identité de cette pharmacie auprès du cloud (officine_id, code)
  - La clé API chiffrée (AES-256-GCM, même clé que les ordonnances)
  - L'URL du cloud

Ces informations sont renseignées lors de l'onboarding initial
et ne changent qu'en cas de rotation de clé.
"""

import base64
import os
import uuid

from django.conf import settings
from django.db import models

# UUID fixe du singleton cloud
CLOUD_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


class OfficineParametrage(models.Model):
    """
    Singleton : paramètres cloud de cette pharmacie.

    La cle_api est stockée chiffrée (AES-256-GCM) via la même
    ORDONNANCE_ENCRYPTION_KEY que les images d'ordonnances.
    Elle n'est jamais accessible en clair depuis la base de données.

    Utilisation :
        config = OfficineParametrage.obtenir()
        if config.est_configure:
            cle = config.cle_api_dechiffree  # property — déchiffre à la volée
    """

    id = models.UUIDField(
        primary_key=True,
        default=CLOUD_SINGLETON_ID,
        editable=False,
    )

    # ── Identité officine côté cloud ──────────────────────────────────────────
    officine_id = models.UUIDField(
        null=True, blank=True,
        help_text="UUID attribué par le cloud lors du provisionnement.",
    )
    code_officine = models.CharField(
        max_length=20, blank=True,
        help_text='Code court de la pharmacie côté cloud (ex: "PHA-001").',
    )

    # ── Connexion cloud ───────────────────────────────────────────────────────
    cloud_api_url = models.URLField(
        blank=True,
        help_text="URL de base de l'API cloud (ex: https://cloud.pharmapp.bf).",
    )
    # La clé API est stockée chiffrée (base64url de nonce || ciphertext || tag)
    cle_api_chiffree = models.TextField(
        blank=True,
        help_text="Clé API chiffrée AES-256-GCM. Ne jamais modifier manuellement.",
    )
    prefixe_cle = models.CharField(
        max_length=12, blank=True,
        help_text='Préfixe non-secret ("phk_XXXX") pour vérification visuelle.',
    )

    # ── Méta ──────────────────────────────────────────────────────────────────
    configure_le   = models.DateTimeField(null=True, blank=True)
    modifie_le     = models.DateTimeField(auto_now=True)
    version_logiciel = models.CharField(
        max_length=20, blank=True,
        help_text="Version du logiciel local (injectée depuis settings.py au démarrage).",
    )

    class Meta:
        app_label    = "parametrage"
        db_table     = "parametrage_officine_cloud"
        verbose_name = "Paramétrage Cloud"

    def __str__(self) -> str:
        if self.est_configure:
            return f"Cloud PharmApp — {self.code_officine} ({self.cloud_api_url})"
        return "Cloud PharmApp — non configuré"

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Force l'identifiant singleton."""
        self.id = CLOUD_SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def obtenir(cls) -> "OfficineParametrage":
        """Retourne le singleton, le crée vide si absent."""
        obj, _ = cls.objects.get_or_create(id=CLOUD_SINGLETON_ID)
        return obj

    @property
    def est_configure(self) -> bool:
        """Retourne True si la connexion cloud est opérationnelle."""
        return bool(
            self.officine_id
            and self.cloud_api_url
            and self.cle_api_chiffree
        )

    @property
    def cle_api_dechiffree(self) -> str:
        """
        Déchiffre et retourne la clé API.
        Lève ValueError si le paramétrage est incomplet ou la clé corrompue.
        """
        if not self.cle_api_chiffree:
            raise ValueError("Clé API cloud non configurée.")
        return _dechiffrer_cle(self.cle_api_chiffree)

    def stocker_cle_api(self, cle_api_brute: str) -> None:
        """
        Chiffre et stocke la clé API brute.
        Appeler .save() après pour persister.
        """
        if not cle_api_brute.startswith("phk_"):
            raise ValueError("Format de clé invalide (doit commencer par 'phk_').")
        self.cle_api_chiffree = _chiffrer_cle(cle_api_brute)
        self.prefixe_cle = cle_api_brute[:8]


# ─── Fonctions de chiffrement (AES-256-GCM) ───────────────────────────────────

def _obtenir_cle_chiffrement() -> bytes:
    """Retourne la clé de chiffrement depuis les settings (même que ordonnances)."""
    cle_b64 = getattr(settings, "ORDONNANCE_ENCRYPTION_KEY", "")
    if not cle_b64:
        raise ValueError(
            "ORDONNANCE_ENCRYPTION_KEY non définie — impossible de chiffrer/déchiffrer la clé API cloud."
        )
    try:
        cle = base64.urlsafe_b64decode(cle_b64)
        if len(cle) != 32:
            raise ValueError("La clé doit faire exactement 32 octets décodés.")
        return cle
    except Exception as exc:
        raise ValueError(f"ORDONNANCE_ENCRYPTION_KEY invalide : {exc}") from exc


def _chiffrer_cle(cle_api_brute: str) -> str:
    """Chiffre la clé API via AES-256-GCM. Retourne base64url(nonce || ciphertext || tag)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    cle = _obtenir_cle_chiffrement()
    nonce = os.urandom(12)
    aad = b"cloud-api-key-v1"  # AAD dédié — empêche la substitution

    aesgcm = AESGCM(cle)
    donnees_chiffrees = aesgcm.encrypt(nonce, cle_api_brute.encode("utf-8"), aad)

    # Format : nonce (12) || ciphertext+tag
    blob = nonce + donnees_chiffrees
    return base64.urlsafe_b64encode(blob).decode("ascii")


def _dechiffrer_cle(blob_b64: str) -> str:
    """Déchiffre un blob AES-256-GCM stocké. Retourne la clé API brute."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    cle = _obtenir_cle_chiffrement()
    aad = b"cloud-api-key-v1"

    try:
        blob = base64.urlsafe_b64decode(blob_b64)
        nonce = blob[:12]
        ciphertext = blob[12:]
        aesgcm = AESGCM(cle)
        return aesgcm.decrypt(nonce, ciphertext, aad).decode("utf-8")
    except (InvalidTag, Exception) as exc:
        raise ValueError(f"Impossible de déchiffrer la clé API cloud : {exc}") from exc
