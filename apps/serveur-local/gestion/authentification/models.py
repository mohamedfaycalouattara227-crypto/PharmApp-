"""
gestion/authentification/models.py
Modèle utilisateur personnalisé PharmApp — 7 rôles hiérarchiques.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class RoleUtilisateur(models.TextChoices):
    STAGIAIRE           = "stagiaire",           "Stagiaire"
    CAISSIER            = "caissier",            "Caissier(ère)"
    ASSISTANT           = "assistant",           "Pharmacien(ne) assistant(e)"
    GESTIONNAIRE_STOCK  = "gestionnaire_stock",  "Gestionnaire de stock"
    PHARMACIEN_ADJOINT  = "pharmacien_adjoint",  "Pharmacien(ne) adjoint(e)"
    TITULAIRE           = "titulaire",           "Pharmacien(ne) titulaire"
    ADMINISTRATEUR      = "administrateur",      "Administrateur système"


HIERARCHIE_ROLES = {
    RoleUtilisateur.STAGIAIRE:          0,
    RoleUtilisateur.CAISSIER:           1,
    RoleUtilisateur.ASSISTANT:          2,
    RoleUtilisateur.GESTIONNAIRE_STOCK: 3,
    RoleUtilisateur.PHARMACIEN_ADJOINT: 4,
    RoleUtilisateur.TITULAIRE:          5,
    RoleUtilisateur.ADMINISTRATEUR:     6,
}


class GestionnaireUtilisateur(BaseUserManager):
    def create_user(self, email, mot_de_passe=None, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire.")
        email = self.normalize_email(email)
        extra_fields.pop("username", None)  # compat tests / API Django classique
        secret = mot_de_passe if mot_de_passe is not None else password
        utilisateur = self.model(email=email, **extra_fields)
        utilisateur.set_password(secret)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, email, mot_de_passe=None, password=None, **extra_fields):
        extra_fields.setdefault("role", RoleUtilisateur.ADMINISTRATEUR)
        extra_fields.setdefault("est_actif", True)
        secret = mot_de_passe if mot_de_passe is not None else password
        return self.create_user(email, mot_de_passe=secret, **extra_fields)


class UtilisateurPharmacien(AbstractBaseUser):
    """Utilisateur du système de pharmacie avec rôle hiérarchique."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Adresse e-mail")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    role = models.CharField(
        max_length=30,
        choices=RoleUtilisateur.choices,
        default=RoleUtilisateur.CAISSIER,
        verbose_name="Rôle",
    )
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    numero_ordre = models.CharField(
        max_length=50, blank=True,
        verbose_name="Numéro d'ordre (pharmaciens diplômés)",
    )
    est_actif = models.BooleanField(default=True, verbose_name="Compte actif")
    est_verrouille = models.BooleanField(default=False, verbose_name="Compte verrouillé")
    tentatives_connexion_echouees = models.PositiveSmallIntegerField(default=0)
    verrouille_jusqu_au = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)
    derniere_connexion_reussie = models.DateTimeField(null=True, blank=True)

    objects = GestionnaireUtilisateur()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["prenom", "nom", "role"]

    class Meta:
        db_table = "authentification_utilisateur"
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.nom_complet} ({self.get_role_display()})"

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()

    @property
    def est_pharmacien(self) -> bool:
        return self.role in (
            RoleUtilisateur.PHARMACIEN_ADJOINT,
            RoleUtilisateur.TITULAIRE,
        )

    @property
    def niveau_role(self) -> int:
        return HIERARCHIE_ROLES.get(self.role, -1)

    def a_permission_role(self, role_requis: str) -> bool:
        """Vérifie si l'utilisateur a au moins le rôle requis."""
        niveau_requis = HIERARCHIE_ROLES.get(role_requis, 99)
        return self.niveau_role >= niveau_requis

    def incrementer_echec_connexion(self):
        from django.conf import settings
        self.tentatives_connexion_echouees += 1
        max_tentatives = getattr(settings, "TENTATIVES_CONNEXION_MAX", 5)
        if self.tentatives_connexion_echouees >= max_tentatives:
            duree = getattr(settings, "DUREE_BLOCAGE_COMPTE_MINUTES", 30)
            from datetime import timedelta
            self.est_verrouille = True
            self.verrouille_jusqu_au = timezone.now() + timedelta(minutes=duree)
        self.save(update_fields=[
            "tentatives_connexion_echouees", "est_verrouille", "verrouille_jusqu_au"
        ])

    def reinitialiser_echecs_connexion(self):
        self.tentatives_connexion_echouees = 0
        self.est_verrouille = False
        self.verrouille_jusqu_au = None
        self.derniere_connexion_reussie = timezone.now()
        self.save(update_fields=[
            "tentatives_connexion_echouees", "est_verrouille",
            "verrouille_jusqu_au", "derniere_connexion_reussie"
        ])

    @property
    def is_active(self):
        return self.est_actif

    @property
    def is_staff(self):
        return self.role == RoleUtilisateur.ADMINISTRATEUR

    @property
    def is_superuser(self):
        return self.role == RoleUtilisateur.ADMINISTRATEUR

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser
