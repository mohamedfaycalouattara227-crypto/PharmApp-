"""
apps/identite/models.py
Modèle Officine — identité multi-tenant du Cloud PharmApp.

Chaque pharmacie cliente possède une entrée unique dans cette table.
Sa clé API (jamais stockée en clair) lui permet de s'authentifier
auprès de toutes les API cloud.
"""

import uuid
from django.db import models


class StatutAbonnement(models.TextChoices):
    ESSAI    = "essai",    "Essai"
    ACTIF    = "actif",    "Actif"
    SUSPENDU = "suspendu", "Suspendu"
    EXPIRE   = "expire",   "Expiré"


class Officine(models.Model):
    """
    Représente une pharmacie cliente enregistrée sur le Cloud PharmApp.

    Règles de sécurité :
    - cle_api_hash : SHA-256 de la clé brute — jamais la clé en clair.
    - cle_api_prefixe : 8 premiers caractères de la clé ("phk_XXXX")
      permettant à l'admin d'identifier la clé sans la révéler.
    - La clé complète n'est retournée qu'à la création (une seule fois).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique de l'officine, communiqué au serveur local.",
    )
    nom = models.CharField(
        max_length=200,
        help_text="Raison sociale ou nom commercial de la pharmacie.",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text='Code court unique. Exemple : "PHA-001".',
    )
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, default="Burkina Faso")

    # ── Clé API ───────────────────────────────────────────────────────────────
    cle_api_hash = models.CharField(
        max_length=128,
        help_text="SHA-256 hexadécimal de la clé API — jamais la clé en clair.",
    )
    cle_api_prefixe = models.CharField(
        max_length=12,
        help_text="Préfixe non-secret de la clé (ex: 'phk_A1B2') pour identification.",
    )

    # ── Abonnement ────────────────────────────────────────────────────────────
    statut_abonnement = models.CharField(
        max_length=20,
        choices=StatutAbonnement.choices,
        default=StatutAbonnement.ESSAI,
    )
    date_debut_abonnement = models.DateField(null=True, blank=True)
    date_fin_abonnement   = models.DateField(null=True, blank=True)

    # ── Télémétrie (mise à jour par le serveur local) ─────────────────────────
    version_logiciel   = models.CharField(
        max_length=20,
        blank=True,
        help_text="Dernière version déclarée par le serveur local au moment de la connexion.",
    )
    derniere_connexion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Horodatage de la dernière requête reçue depuis ce serveur local.",
    )

    # ── Méta ──────────────────────────────────────────────────────────────────
    est_active  = models.BooleanField(default=True)
    cree_le     = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)
    notes       = models.TextField(blank=True, help_text="Notes internes admin.")

    class Meta:
        app_label = "identite"
        ordering  = ["code"]
        verbose_name = "Officine"
        verbose_name_plural = "Officines"
        indexes = [
            models.Index(fields=["cle_api_hash"]),
            models.Index(fields=["statut_abonnement"]),
            models.Index(fields=["derniere_connexion"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.nom}"

    # ── Compatibilité DRF (throttle, permissions) ─────────────────────────────
    # DRF appelle request.user.is_authenticated dans ScopedRateThrottle
    # et dans plusieurs permissions built-in. Officine n'est pas un AbstractUser,
    # mais doit exposer ces attributs pour s'intégrer correctement.

    @property
    def is_authenticated(self) -> bool:
        """Toujours True : une Officine ne peut exister dans request.user
        que si l'authentification par clé API a réussi."""
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def pk_str(self) -> str:
        """Clé primaire en chaîne — utilisée par ScopedRateThrottle comme cache key."""
        return str(self.pk)

    @property
    def est_en_ligne(self) -> bool:
        """
        Considère l'officine comme "en ligne" si elle s'est connectée
        dans les 5 dernières minutes.
        """
        if not self.derniere_connexion:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - self.derniere_connexion) < timedelta(minutes=5)

    @property
    def abonnement_actif(self) -> bool:
        """Retourne True si l'officine peut synchroniser."""
        return (
            self.est_active
            and self.statut_abonnement in (StatutAbonnement.ACTIF, StatutAbonnement.ESSAI)
        )
