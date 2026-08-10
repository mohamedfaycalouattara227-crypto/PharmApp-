"""
gestion/clients/models.py
Modèle Client — gestion de la clientèle avec crédit, assurance et droit à l'oubli.

AJOUT étape 5 :
  - allergies : données médicales sensibles, visibles uniquement pharmacien_adjoint+ (§7.2 CDC)
"""

import uuid
from decimal import Decimal
from django.db import models


class TypeClient(models.TextChoices):
    PARTICULIER = "particulier", "Particulier"
    ASSURANCE   = "assurance",   "Assurance / Mutuelle"
    INSTITUTION = "institution", "Institution (hôpital, ONG…)"


class Client(models.Model):
    """Client de la pharmacie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=150, verbose_name="Nom")
    prenom = models.CharField(max_length=150, blank=True, verbose_name="Prénom")
    telephone = models.CharField(
        max_length=25, unique=True, blank=True, null=True, verbose_name="Téléphone"
    )
    email = models.EmailField(blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    adresse = models.TextField(blank=True)
    type_client = models.CharField(
        max_length=20,
        choices=TypeClient.choices,
        default=TypeClient.PARTICULIER,
    )

    # Assurance / mutuelle
    assureur = models.CharField(max_length=200, blank=True)
    numero_assurance = models.CharField(max_length=100, blank=True, unique=True, null=True)
    taux_prise_en_charge = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Taux de prise en charge (%)",
    )

    # Crédit
    credit_autorise = models.BooleanField(default=False, verbose_name="Crédit autorisé")
    plafond_credit = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Plafond de crédit (FCFA)",
    )
    encours_credit = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Encours crédit actuel (FCFA)",
    )

    # ── Étape 5 : données médicales sensibles ────────────────────────────────
    allergies = models.TextField(
        blank=True,
        verbose_name="Allergies connues",
        help_text=(
            "Données médicales sensibles. "
            "Visibles uniquement par pharmacien_adjoint et supérieurs (§7.2 CDC). "
            "Un caissier ne doit JAMAIS voir ce champ — restriction appliquée "
            "côté serializer serveur, pas uniquement dans l'UI."
        ),
    )

    # Statut
    est_actif = models.BooleanField(default=True)
    est_anonymise = models.BooleanField(default=False, verbose_name="Données anonymisées (RGPD)")
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clients_client"
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["nom", "prenom"]
        indexes = [
            models.Index(fields=["telephone"]),
            models.Index(fields=["numero_assurance"]),
            models.Index(fields=["est_actif"]),
            models.Index(
                fields=["credit_autorise", "est_actif"],
                name="clients_encours_credit_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(plafond_credit__gte=0),
                name="chk_client_plafond_credit_positif",
                violation_error_message="Le plafond de crédit ne peut pas être négatif.",
            ),
            models.CheckConstraint(
                check=models.Q(taux_prise_en_charge__gte=0)
                & models.Q(taux_prise_en_charge__lte=100),
                name="chk_client_taux_prise_en_charge",
                violation_error_message=(
                    "Le taux de prise en charge doit être compris entre 0 et 100 %."
                ),
            ),
        ]

    def __str__(self):
        if self.est_anonymise:
            return f"[Anonyme] {str(self.id)[:8]}"
        return f"{self.prenom} {self.nom}".strip() or f"Client #{str(self.id)[:8]}"

    @property
    def nom_complet(self) -> str:
        if self.est_anonymise:
            return "[Anonyme]"
        return f"{self.prenom} {self.nom}".strip()

    def anonymiser(self):
        """Droit à l'oubli — supprime les données personnelles identifiables."""
        self.nom = "Anonyme"
        self.prenom = ""
        self.telephone = None
        self.email = ""
        self.date_naissance = None
        self.adresse = ""
        self.notes = ""
        self.allergies = ""
        self.numero_assurance = None
        self.est_anonymise = True
        self.save()
