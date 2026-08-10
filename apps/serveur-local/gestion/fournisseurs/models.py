"""
gestion/fournisseurs/models.py

Modèles Fournisseur, BonCommande, LigneBonCommande, ReceptionBonCommande,
LigneReception. Conçus pour combler l'ancre manquante de la réception de
stock (§4.4.2 du cahier des charges) : chaque réception validée doit être
rattachée à un bon de commande et donc à un fournisseur.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ─── Fournisseur ──────────────────────────────────────────────────────────────


class Fournisseur(models.Model):
    """Un fournisseur pharmaceutique (grossiste, laboratoire, importateur)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Code fournisseur",
        help_text="Identifiant court affiché sur les bons de commande.",
    )
    nom = models.CharField(max_length=200)
    contact_principal = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, default="Burkina Faso")

    numero_agrement = models.CharField(
        max_length=60, blank=True,
        verbose_name="N° d'agrément pharmaceutique",
    )
    delai_livraison_jours = models.PositiveIntegerField(
        default=7,
        verbose_name="Délai de livraison indicatif (jours)",
    )
    conditions_paiement = models.CharField(
        max_length=200, blank=True,
        help_text="Ex. « 30 jours net », « comptant »…",
    )

    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "fournisseurs"
        db_table = "fournisseurs_fournisseur"
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["actif", "nom"]),
        ]

    def __str__(self):
        return f"{self.code} — {self.nom}"


# ─── Bon de commande ──────────────────────────────────────────────────────────


class StatutBonCommande(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    ENVOYE    = "envoye",    "Envoyé au fournisseur"
    PARTIEL   = "partiel",   "Reçu partiellement"
    RECU      = "recu",      "Reçu intégralement"
    CLOTURE   = "cloture",   "Clôturé"
    ANNULE    = "annule",    "Annulé"


class BonCommande(models.Model):
    """
    Bon de commande émis vers un fournisseur.

    Cycle de vie : BROUILLON → ENVOYE → (PARTIEL) → RECU → CLOTURE
                                       ↘ ANNULE
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(
        max_length=30, unique=True,
        verbose_name="Numéro de bon de commande",
        help_text="Séquentiel — généré par le service, jamais saisi.",
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name="bons_commande",
    )
    statut = models.CharField(
        max_length=15,
        choices=StatutBonCommande.choices,
        default=StatutBonCommande.BROUILLON,
    )

    # `timezone.now` renvoie un datetime : sur un DateField cela produit une
    # valeur non conforme (erreur de sérialisation DRF). La date du jour locale
    # est la sémantique attendue pour une date de commande.
    date_commande = models.DateField(default=timezone.localdate)
    date_livraison_prevue = models.DateField(null=True, blank=True)

    total_ht  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_tva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bons_commande_crees",
    )
    envoye_le = models.DateTimeField(null=True, blank=True)
    cloture_le = models.DateTimeField(null=True, blank=True)
    annule_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.TextField(blank=True)

    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "fournisseurs"
        db_table = "fournisseurs_bon_commande"
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["numero"]),
            models.Index(fields=["fournisseur", "statut"]),
            models.Index(fields=["statut", "-cree_le"]),
        ]

    def __str__(self):
        return f"BC {self.numero} — {self.fournisseur.nom}"

    # ─── Aides d'état ────────────────────────────────────────────────────────

    def est_modifiable(self) -> bool:
        return self.statut == StatutBonCommande.BROUILLON

    def est_receptionnable(self) -> bool:
        return self.statut in (StatutBonCommande.ENVOYE, StatutBonCommande.PARTIEL)

    def recalculer_totaux(self) -> None:
        """Recalcule les totaux à partir des lignes (source de vérité)."""
        agrege = self.lignes.aggregate(
            ht=models.Sum(models.F("prix_unitaire_ht") * models.F("quantite_commandee")),
        )
        total_ht = agrege["ht"] or Decimal("0.00")
        # TVA moyenne pondérée
        total_tva = Decimal("0.00")
        for ligne in self.lignes.all():
            base = ligne.prix_unitaire_ht * ligne.quantite_commandee
            total_tva += (base * ligne.taux_tva / Decimal("100")).quantize(Decimal("0.01"))
        self.total_ht  = total_ht.quantize(Decimal("0.01"))
        self.total_tva = total_tva
        self.total_ttc = (self.total_ht + self.total_tva).quantize(Decimal("0.01"))


class LigneBonCommande(models.Model):
    """Ligne d'un bon de commande : un médicament, une quantité, un prix."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bon_commande = models.ForeignKey(
        BonCommande, on_delete=models.CASCADE, related_name="lignes"
    )
    medicament = models.ForeignKey(
        "catalogue.Medicament", on_delete=models.PROTECT,
        related_name="lignes_bon_commande",
    )
    quantite_commandee = models.PositiveIntegerField()
    quantite_recue = models.PositiveIntegerField(
        default=0,
        help_text="Cumul des réceptions successives, ≤ quantite_commandee.",
    )
    prix_unitaire_ht = models.DecimalField(max_digits=10, decimal_places=2)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        verbose_name="Taux de TVA (%)",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = "fournisseurs"
        db_table = "fournisseurs_bon_commande_ligne"
        verbose_name = "Ligne de bon de commande"
        verbose_name_plural = "Lignes de bon de commande"
        ordering = ["bon_commande", "medicament__nom"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantite_recue__lte=models.F("quantite_commandee")),
                name="ligne_bc_recue_lte_commandee",
            ),
        ]

    def __str__(self):
        return f"{self.medicament.nom} × {self.quantite_commandee}"

    @property
    def quantite_restante(self) -> int:
        return self.quantite_commandee - self.quantite_recue

    @property
    def est_solde(self) -> bool:
        return self.quantite_recue >= self.quantite_commandee


# ─── Réception ────────────────────────────────────────────────────────────────


class ReceptionBonCommande(models.Model):
    """
    Réception (totale ou partielle) d'un bon de commande.
    Une même BC peut avoir plusieurs réceptions successives.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bon_commande = models.ForeignKey(
        BonCommande, on_delete=models.PROTECT, related_name="receptions"
    )
    numero_bordereau = models.CharField(
        max_length=60, blank=True,
        verbose_name="N° bordereau du fournisseur",
    )
    date_reception = models.DateTimeField(default=timezone.now)
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="receptions_effectuees",
    )
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "fournisseurs"
        db_table = "fournisseurs_reception"
        verbose_name = "Réception de commande"
        verbose_name_plural = "Réceptions de commande"
        ordering = ["-date_reception"]
        indexes = [
            models.Index(fields=["bon_commande", "-date_reception"]),
        ]

    def __str__(self):
        return f"Réception {self.bon_commande.numero} — {self.date_reception:%Y-%m-%d}"


class LigneReception(models.Model):
    """
    Ligne d'une réception : quantité effectivement reçue pour une ligne de BC,
    avec le lot et la date de péremption qui alimentent le stock.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reception = models.ForeignKey(
        ReceptionBonCommande, on_delete=models.CASCADE, related_name="lignes"
    )
    ligne_bon_commande = models.ForeignKey(
        LigneBonCommande, on_delete=models.PROTECT, related_name="receptions"
    )
    lot = models.ForeignKey(
        "catalogue.Lot",
        on_delete=models.PROTECT,
        related_name="receptions",
        null=True, blank=True,
        help_text="Lot créé (ou complété) par cette réception.",
    )
    quantite_recue = models.PositiveIntegerField()
    numero_lot = models.CharField(max_length=60)
    date_peremption = models.DateField()
    prix_achat_unitaire = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "fournisseurs"
        db_table = "fournisseurs_reception_ligne"
        verbose_name = "Ligne de réception"
        verbose_name_plural = "Lignes de réception"

    def __str__(self):
        return f"{self.ligne_bon_commande.medicament.nom} × {self.quantite_recue}"
