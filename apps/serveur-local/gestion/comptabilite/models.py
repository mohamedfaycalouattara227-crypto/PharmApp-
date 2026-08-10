"""
gestion/comptabilite/models.py
Modèles comptables : EcritureComptable.
"""

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class TypeEcriture(models.TextChoices):
    RECETTE  = "recette",  "Recette"
    DEPENSE  = "depense",  "Dépense"
    ACHAT    = "achat",    "Achat fournisseur"
    SALAIRE  = "salaire",  "Charge salariale"
    REMISE   = "remise",   "Remise accordée"
    CREDIT   = "credit",   "Créance client"
    RECOUVREMENT = "recouvrement", "Recouvrement créance"


class EcritureComptable(models.Model):
    """Écriture comptable liée aux opérations de la pharmacie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_ecriture = models.CharField(max_length=20, choices=TypeEcriture.choices)
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant (FCFA)"
    )
    description = models.TextField()
    reference_document = models.CharField(
        max_length=100, blank=True,
        verbose_name="Référence (n° vente, facture fournisseur…)",
    )
    id_vente = models.UUIDField(null=True, blank=True)
    id_cloture = models.UUIDField(null=True, blank=True)
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ecritures_comptables",
    )
    date_ecriture = models.DateField()
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comptabilite_ecriture"
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Écritures comptables"
        ordering = ["-date_ecriture", "-cree_le"]
        indexes = [
            models.Index(fields=["date_ecriture"]),
            models.Index(fields=["type_ecriture", "date_ecriture"]),
            models.Index(
                fields=["type_ecriture", "date_ecriture"], name="compta_type_date_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(montant__gt=0),
                name="chk_ecriture_montant_positif",
                violation_error_message=(
                    "Le montant d'une écriture comptable doit être strictement positif."
                ),
            ),
        ]

    def __str__(self):
        return f"[{self.get_type_ecriture_display()}] {self.montant} FCFA — {self.date_ecriture}"
