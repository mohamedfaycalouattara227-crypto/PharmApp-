"""
gestion/catalogue/models.py
Modèles du catalogue : CategorieProduit, Medicament, Lot.
Gestion FEFO (First Expired, First Out) pour les lots.

AJOUT étape 4 :
  - prix_reglemente  : booléen — si True, prix_reference est le plafond légal
  - prix_reference   : prix plafonné (OHADA/CAMEG) quand prix_reglemente=True
  - hors_nomenclature: produit non listé dans le référentiel national → prix libre
"""

import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class CategorieProduit(models.Model):
    """Catégorie thérapeutique ou commerciale d'un médicament."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=150, unique=True, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Code")
    est_active = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogue_categorie"
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Medicament(models.Model):
    """Médicament du catalogue de la pharmacie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=250, verbose_name="Nom commercial")
    denomination_commune_internationale = models.CharField(
        max_length=250, blank=True, verbose_name="DCI"
    )
    code_cis = models.CharField(
        max_length=50, unique=True, null=True, blank=True,
        verbose_name="Code CIS (identifiant unique)",
    )
    code_barre = models.CharField(max_length=50, blank=True)
    categorie = models.ForeignKey(
        CategorieProduit,
        on_delete=models.PROTECT,
        related_name="medicaments",
        verbose_name="Catégorie",
        null=True, blank=True,
    )
    forme_pharmaceutique = models.CharField(
        max_length=100, blank=True,
        verbose_name="Forme (comprimé, sirop, injectable…)",
    )
    dosage = models.CharField(max_length=100, blank=True, verbose_name="Dosage")
    conditionnement = models.CharField(
        max_length=100, blank=True,
        verbose_name="Conditionnement (boîte de 12, etc.)",
    )
    fabricant = models.CharField(max_length=200, blank=True)
    pays_origine = models.CharField(max_length=100, blank=True)

    # Tarification (en FCFA)
    prix_public = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Prix public (FCFA)",
        default=Decimal("0.00"),
    )
    prix_min_autorise = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Prix minimum autorisé",
    )
    prix_max_autorise = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Prix maximum autorisé",
    )
    taux_remise_max = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal("10.00"),
        verbose_name="Remise maximale autorisée (%)",
    )

    # ── Étape 4 : prix réglementé & hors nomenclature ────────────────────────
    prix_reglemente = models.BooleanField(
        default=False,
        verbose_name="Prix réglementé (CAMEG/OHADA)",
        help_text="Si True, le prix de vente ne peut pas dépasser prix_reference.",
    )
    prix_reference = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="Prix de référence réglementé (FCFA)",
        help_text="Plafond légal, obligatoire si prix_reglemente=True.",
    )
    hors_nomenclature = models.BooleanField(
        default=False,
        verbose_name="Hors nomenclature nationale",
        help_text="Produit absent du référentiel CAMEG — prix libre sans plafond.",
    )

    # Contrôles & restrictions
    necessite_ordonnance = models.BooleanField(
        default=False, verbose_name="Médicament sur ordonnance"
    )
    est_produit_controle = models.BooleanField(
        default=False, verbose_name="Stupéfiant / psychotrope"
    )
    est_actif = models.BooleanField(default=True, verbose_name="Actif dans le catalogue")

    # Alertes stock
    seuil_alerte_stock = models.PositiveIntegerField(
        default=20, verbose_name="Seuil d'alerte de stock (unités)"
    )
    seuil_rupture_stock = models.PositiveIntegerField(
        default=5, verbose_name="Seuil de rupture de stock (unités)"
    )

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogue_medicament"
        verbose_name = "Médicament"
        verbose_name_plural = "Médicaments"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["code_cis"]),
            models.Index(fields=["code_barre"]),
            models.Index(fields=["est_actif"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.dosage})" if self.dosage else self.nom

    @property
    def stock_total_disponible(self) -> int:
        return self.lots.filter(
            est_actif=True,
            date_peremption__gt=timezone.now().date(),
        ).aggregate(
            total=models.Sum("quantite_disponible")
        )["total"] or 0

    @property
    def est_en_alerte_stock(self) -> bool:
        return self.stock_total_disponible <= self.seuil_alerte_stock

    @property
    def est_en_rupture(self) -> bool:
        return self.stock_total_disponible <= self.seuil_rupture_stock


class Lot(models.Model):
    """
    Lot de médicaments reçu d'un fournisseur.
    Unité de gestion FEFO (First Expired, First Out).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medicament = models.ForeignKey(
        Medicament, on_delete=models.PROTECT,
        related_name="lots", verbose_name="Médicament",
    )
    numero_lot = models.CharField(max_length=100, verbose_name="Numéro de lot fabricant")
    numero_lot_interne = models.CharField(
        max_length=50, unique=True, blank=True,
        verbose_name="Référence interne",
    )
    date_fabrication = models.DateField(null=True, blank=True)
    date_peremption = models.DateField(verbose_name="Date de péremption")
    quantite_initiale = models.PositiveIntegerField(verbose_name="Quantité réceptionnée")
    quantite_disponible = models.PositiveIntegerField(verbose_name="Quantité disponible")
    prix_achat_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Prix d'achat unitaire (FCFA)",
    )
    fournisseur = models.CharField(max_length=200, blank=True)
    bon_commande = models.CharField(max_length=100, blank=True)
    emplacement_stockage = models.CharField(
        max_length=100, blank=True, verbose_name="Emplacement (rayon/casier)"
    )
    est_actif = models.BooleanField(default=True, verbose_name="Lot actif")
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalogue_lot"
        verbose_name = "Lot"
        verbose_name_plural = "Lots"
        ordering = ["date_peremption"]  # FEFO par défaut
        indexes = [
            models.Index(fields=["medicament", "date_peremption"]),
            models.Index(fields=["est_actif"]),
            models.Index(fields=["date_peremption"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantite_disponible__gte=0),
                name="chk_lot_quantite_disponible_pos",
                violation_error_message="La quantité disponible d'un lot ne peut pas être négative.",
            ),
            models.CheckConstraint(
                check=models.Q(quantite_initiale__gte=0),
                name="chk_lot_quantite_initiale_pos",
                violation_error_message="La quantité initiale d'un lot ne peut pas être négative.",
            ),
            models.CheckConstraint(
                check=models.Q(prix_achat_unitaire__gte=0),
                name="chk_lot_prix_achat_positif",
                violation_error_message="Le prix d'achat unitaire ne peut pas être négatif.",
            ),
        ]

    def __str__(self):
        return f"{self.medicament.nom} — Lot {self.numero_lot} (exp. {self.date_peremption})"

    @property
    def est_perime(self) -> bool:
        return self.date_peremption < timezone.now().date()

    @property
    def jours_avant_peremption(self) -> int:
        delta = self.date_peremption - timezone.now().date()
        return delta.days

    @property
    def est_perimant_bientot(self) -> bool:
        """Vrai si le lot périme dans moins de 90 jours."""
        return 0 <= self.jours_avant_peremption <= 90
