"""
gestion/stocks/models.py
Modèles de gestion des stocks : MouvementStock, AlerteStock, Inventaire, LigneInventaire.
"""

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class TypeMouvement(models.TextChoices):
    RECEPTION       = "reception",       "Réception fournisseur"
    VENTE           = "vente",           "Sortie vente"
    RETOUR_CLIENT   = "retour_client",   "Retour client"
    AJUSTEMENT_PLUS = "ajustement_plus", "Ajustement positif (inventaire)"
    AJUSTEMENT_MOINS= "ajustement_moins","Ajustement négatif (inventaire)"
    PEREMPTION      = "peremption",      "Mise au rebut (périmé)"
    TRANSFERT_ENTREE= "transfert_entree","Transfert entrant"
    TRANSFERT_SORTIE= "transfert_sortie","Transfert sortant"
    PERTE           = "perte",           "Perte / vol constaté"


class MouvementStock(models.Model):
    """Journal de tous les mouvements de stock."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(
        "catalogue.Lot", on_delete=models.PROTECT, related_name="mouvements"
    )
    type_mouvement = models.CharField(max_length=20, choices=TypeMouvement.choices)
    quantite = models.IntegerField(
        verbose_name="Quantité (positive=entrée, négative=sortie)"
    )
    quantite_avant = models.PositiveIntegerField(verbose_name="Stock avant mouvement")
    quantite_apres = models.PositiveIntegerField(verbose_name="Stock après mouvement")
    motif = models.TextField(blank=True)
    reference_document = models.CharField(
        max_length=100, blank=True,
        verbose_name="Réf. document (n° vente, bon commande…)",
    )
    effectue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mouvements_stock",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stocks_mouvement"
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["lot", "cree_le"]),
            models.Index(fields=["type_mouvement", "cree_le"]),
            models.Index(
                fields=["effectue_par", "cree_le"], name="stocks_mouv_effectue_par_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantite_avant__gte=0),
                name="chk_mouvement_quantite_avant_pos",
                violation_error_message="La quantité avant mouvement ne peut pas être négative.",
            ),
            models.CheckConstraint(
                check=models.Q(quantite_apres__gte=0),
                name="chk_mouvement_quantite_apres_pos",
                violation_error_message="La quantité après mouvement ne peut pas être négative.",
            ),
        ]

    def __str__(self):
        signe = "+" if self.quantite > 0 else ""
        return f"{self.lot.medicament.nom} {signe}{self.quantite} ({self.get_type_mouvement_display()})"


class NiveauAlerte(models.TextChoices):
    ALERTE  = "alerte",  "Alerte (stock bas)"
    RUPTURE = "rupture", "Rupture de stock"


class AlerteStock(models.Model):
    """Alerte générée automatiquement quand le stock passe sous le seuil."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medicament = models.ForeignKey(
        "catalogue.Medicament", on_delete=models.CASCADE, related_name="alertes_stock"
    )
    niveau = models.CharField(max_length=10, choices=NiveauAlerte.choices)
    stock_au_moment_alerte = models.PositiveIntegerField()
    seuil_depasse = models.PositiveIntegerField()
    est_resolue = models.BooleanField(default=False)
    resolue_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stocks_alerte"
        verbose_name = "Alerte de stock"
        verbose_name_plural = "Alertes de stock"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["est_resolue"]),
            models.Index(fields=["medicament"]),
        ]

    def __str__(self):
        return f"[{self.niveau.upper()}] {self.medicament.nom} — {self.stock_au_moment_alerte} unités"


class StatutInventaire(models.TextChoices):
    EN_COURS  = "en_cours",  "En cours"
    TERMINE   = "termine",   "Terminé"
    VALIDE    = "valide",    "Validé"
    ANNULE    = "annule",    "Annulé"


class Inventaire(models.Model):
    """Session d'inventaire physique."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=50, unique=True)
    statut = models.CharField(
        max_length=15, choices=StatutInventaire.choices, default=StatutInventaire.EN_COURS
    )
    demarre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventaires_demarre",
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="inventaires_valides",
    )
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    termine_le = models.DateTimeField(null=True, blank=True)
    valide_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "stocks_inventaire"
        verbose_name = "Inventaire"
        verbose_name_plural = "Inventaires"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"Inventaire {self.reference} — {self.get_statut_display()}"


class LigneInventaire(models.Model):
    """Comptage d'un lot lors d'un inventaire."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventaire = models.ForeignKey(
        Inventaire, on_delete=models.CASCADE, related_name="lignes"
    )
    lot = models.ForeignKey(
        "catalogue.Lot", on_delete=models.PROTECT, related_name="lignes_inventaire"
    )
    quantite_systeme = models.PositiveIntegerField(verbose_name="Quantité système")
    quantite_comptee = models.PositiveIntegerField(verbose_name="Quantité comptée physiquement")
    ecart = models.IntegerField(
        default=0, verbose_name="Écart (compté - système)"
    )
    ecart_pourcent = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    notes = models.TextField(blank=True)
    compte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comptages_inventaire",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stocks_ligne_inventaire"
        verbose_name = "Ligne d'inventaire"
        verbose_name_plural = "Lignes d'inventaire"
        unique_together = [("inventaire", "lot")]

    def save(self, *args, **kwargs):
        self.ecart = self.quantite_comptee - self.quantite_systeme
        if self.quantite_systeme > 0:
            self.ecart_pourcent = (
                abs(self.ecart) / Decimal(self.quantite_systeme) * 100
            ).quantize(Decimal("0.01"))
        else:
            self.ecart_pourcent = Decimal("100.00") if self.quantite_comptee > 0 else Decimal("0.00")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lot.medicament.nom} — écart : {self.ecart:+d}"
