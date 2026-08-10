"""Modèles du domaine des ventes PharmApp.

Ce module contient les modèles runtime alignés sur les migrations 0001 à 0006.
"""
from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models


class StatutVente(models.TextChoices):
    EN_COURS = "en_cours", "En cours"
    VALIDEE = "validee", "Validée"
    ANNULEE = "annulee", "Annulée"
    AVOIR = "avoir", "Avoir (note de crédit)"


class ModePaiement(models.TextChoices):
    ESPECES = "especes", "Espèces"
    MOBILE_MONEY = "mobile_money", "Mobile Money (Orange/Moov)"
    ASSURANCE = "assurance", "Assurance / Mutuelle"
    CREDIT = "credit", "Crédit client"
    CHEQUE = "cheque", "Chèque"


class Vente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=30, unique=True, verbose_name="Numéro de vente")
    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventes_effectuees", verbose_name="Vendeur")
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, related_name="ventes", null=True, blank=True, verbose_name="Client (optionnel)")
    ordonnance = models.ForeignKey("ordonnances.Ordonnance", on_delete=models.SET_NULL, related_name="ventes", null=True, blank=True)
    statut = models.CharField(max_length=20, choices=StatutVente.choices, default=StatutVente.VALIDEE)
    mode_paiement = models.CharField(max_length=20, choices=ModePaiement.choices, default=ModePaiement.ESPECES)
    sous_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_remise = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_encaisse = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_rendu = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_assurance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Montant pris en charge par l'assurance")
    reference_mobile_money = models.CharField(max_length=100, blank=True, verbose_name="Référence transaction Mobile Money", help_text="Numéro de confirmation Orange Money / Moov Money.")
    vente_origine = models.ForeignKey("self", on_delete=models.SET_NULL, related_name="avoirs", null=True, blank=True, verbose_name="Vente d'origine (avoirs uniquement)")
    annule_le = models.DateTimeField(null=True, blank=True)
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="ventes_annulees", null=True, blank=True)
    motif_annulation = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    nb_impressions = models.PositiveIntegerField(default=0, help_text="Compteur d'impressions du reçu.")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ventes_vente"
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["statut", "cree_le"]),
            models.Index(fields=["vendeur", "cree_le"]),
            models.Index(fields=["client", "statut"]),
            models.Index(fields=["numero"]),
            models.Index(fields=["cree_le"], name="ventes_vent_cree_le_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(montant_total__gte=0), name="chk_vente_montant_total_positif"),
            models.CheckConstraint(check=models.Q(montant_encaisse__gte=0), name="chk_vente_montant_encaisse_positif"),
            models.CheckConstraint(check=models.Q(montant_rendu__gte=0), name="chk_vente_montant_rendu_positif"),
            models.CheckConstraint(check=models.Q(sous_total__gte=0), name="chk_vente_sous_total_positif"),
        ]

    def __str__(self):
        return self.numero


class LigneVente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey("catalogue.Medicament", on_delete=models.PROTECT, related_name="lignes_vente")
    lot = models.ForeignKey("catalogue.Lot", on_delete=models.PROTECT, related_name="lignes_vente", null=True, blank=True)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    taux_remise = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    prix_unitaire_apres_remise = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "ventes_ligne_vente"
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    @property
    def montant_ligne(self):
        return self.montant_total


class ClotureCaisse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date_cloture = models.DateField(unique=True, verbose_name="Date de clôture")
    caissier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clotures_effectuees")
    validee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="clotures_validees", null=True, blank=True)
    fond_caisse_ouverture = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fond_caisse_cloture = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recettes_especes = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recettes_mobile_money = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recettes_assurance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recettes_credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recettes_cheque = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    chiffre_affaires = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    nombre_ventes = models.PositiveIntegerField(default=0)
    nombre_annulations = models.PositiveIntegerField(default=0)
    ecart_caisse = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="Écart de caisse (FCFA)")
    statut = models.CharField(max_length=15, choices=(("en_cours", "En cours"), ("cloturee", "Clôturée"), ("validee", "Validée")), default="en_cours")
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ventes_cloture_caisse"
        verbose_name = "Clôture de caisse"
        verbose_name_plural = "Clôtures de caisse"
        ordering = ["-date_cloture"]

    def __str__(self):
        return str(self.date_cloture)
