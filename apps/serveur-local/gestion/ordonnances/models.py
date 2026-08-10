"""
gestion/ordonnances/models.py
Modèle Ordonnance — stockage chiffré AES-256 des images médicales.
Les images ne sont JAMAIS synchronisées vers le cloud.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class StatutOrdonnance(models.TextChoices):
    EN_ATTENTE  = "en_attente",  "En attente de vérification"
    VALIDEE     = "validee",     "Validée par pharmacien"
    UTILISEE    = "utilisee",    "Utilisée (dispensée)"
    REFUSEE     = "refusee",     "Refusée"
    EXPIREE     = "expiree",     "Expirée (> 3 mois)"


class Ordonnance(models.Model):
    """
    Ordonnance médicale numérisée.
    L'image est chiffrée avec AES-256-GCM avant stockage.
    Le vecteur d'initialisation est stocké séparément de la clé.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_interne = models.CharField(
        max_length=50, unique=True, verbose_name="Numéro interne"
    )
    # Le client peut être inconnu au moment de la numérisation : l'ordonnance
    # est scannée au comptoir puis rattachée au client lors de la vente.
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="ordonnances",
        null=True,
        blank=True,
        verbose_name="Client",
    )
    prescripteur_nom = models.CharField(
        max_length=200, verbose_name="Nom du médecin prescripteur"
    )
    prescripteur_etablissement = models.CharField(
        max_length=300, blank=True, verbose_name="Établissement de santé"
    )
    date_prescription = models.DateField(verbose_name="Date de prescription")
    date_expiration = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'expiration (généralement 3 mois après prescription)",
    )

    # Chiffrement AES-256-GCM
    image_chiffree = models.BinaryField(
        null=True, blank=True,
        verbose_name="Image chiffrée (AES-256-GCM)",
    )
    vecteur_initialisation = models.BinaryField(
        null=True, blank=True,
        verbose_name="Vecteur d'initialisation AES",
    )
    type_mime = models.CharField(
        max_length=50, blank=True, default="image/jpeg",
        verbose_name="Type MIME de l'image originale",
    )
    taille_image_octets = models.PositiveIntegerField(default=0)

    statut = models.CharField(
        max_length=20, choices=StatutOrdonnance.choices,
        default=StatutOrdonnance.EN_ATTENTE,
    )
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordonnances_validees",
    )
    validee_le = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    numerisee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ordonnances_numerisees",
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ordonnances_ordonnance"
        verbose_name = "Ordonnance"
        verbose_name_plural = "Ordonnances"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["client", "statut"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["cree_le"], name="ordonnances_cree_le_idx"),
            models.Index(
                fields=["date_prescription"], name="ord_date_prescription_idx"
            ),
        ]

    def __str__(self):
        return (
            f"Ordonnance {self.numero_interne} — "
            f"{self.client.nom_complet if self.client_id else 'client non rattaché'}"
        )

    @property
    def est_expiree(self) -> bool:
        if self.date_expiration:
            return self.date_expiration < timezone.now().date()
        # Validité par défaut : 3 mois
        from datetime import timedelta
        return (timezone.now().date() - self.date_prescription).days > 90

    @property
    def a_image(self) -> bool:
        return bool(self.image_chiffree)
