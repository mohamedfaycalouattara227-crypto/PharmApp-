"""
gestion/parametrage/models.py
Singleton de paramétrage de la pharmacie (§3.1 du cahier des charges).

Un seul enregistrement est jamais créé (identifiant UUID fixe SINGLETON_ID),
accessible via `Parametrage.obtenir()`. Le signal post_migrate crée
automatiquement cet enregistrement au premier démarrage.
"""

import uuid
from django.db import models

# UUID fixe du singleton — même pattern que EtatSynchronisation.
PARAMETRAGE_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class TypeImprimante(models.TextChoices):
    THERMIQUE = "thermique", "Thermique 80 mm"
    A4        = "a4",        "Feuille A4"


class Parametrage(models.Model):
    """
    Paramétrage unique de la pharmacie.
    Ne jamais créer de second enregistrement — utiliser `obtenir()`.
    """

    id = models.UUIDField(
        primary_key=True,
        default=PARAMETRAGE_SINGLETON_ID,
        editable=False,
    )

    # ── Identité officine ──────────────────────────────────────────────────
    nom_pharmacie   = models.CharField(max_length=200, default="Pharmacie")
    adresse         = models.TextField(blank=True)
    telephone       = models.CharField(max_length=30, blank=True)
    email           = models.EmailField(blank=True)
    ville           = models.CharField(max_length=100, default="Bobo-Dioulasso")
    numero_agrement = models.CharField(max_length=100, blank=True)
    logo            = models.ImageField(
        upload_to="parametrage/logos/",
        null=True, blank=True,
    )

    # ── Facturation ─────────────────────────────────────────────────────────
    devise              = models.CharField(max_length=10, default="FCFA")
    format_numerotation = models.CharField(
        max_length=50, default="VTE-{YYYY}-{NNNN}",
        help_text="Gabarit de numérotation : {YYYY}=année, {MM}=mois, {NNNN}=séquence",
    )

    # ── Alertes & seuils ────────────────────────────────────────────────────
    seuil_alerte_stock_jours = models.PositiveIntegerField(
        default=20,
        help_text="Quantité minimale en unités déclenchant une alerte de stock bas",
    )
    seuil_peremption_jours = models.PositiveIntegerField(
        default=60,
        help_text="Nombre de jours avant péremption déclenchant une alerte",
    )

    # ── Impression ─────────────────────────────────────────────────────────
    type_imprimante = models.CharField(
        max_length=20,
        choices=TypeImprimante.choices,
        default=TypeImprimante.THERMIQUE,
    )

    # ── Sécurité ────────────────────────────────────────────────────────────
    timeout_inactivite_minutes   = models.PositiveIntegerField(default=30)
    nb_tentatives_connexion_max  = models.PositiveIntegerField(default=5)

    # ── Méta ────────────────────────────────────────────────────────────────
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "parametrage"
        db_table     = "parametrage"
        verbose_name = "Paramétrage"

    def __str__(self) -> str:
        return f"Paramétrage — {self.nom_pharmacie}"

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Force l'identifiant singleton pour empêcher toute duplication."""
        self.id = PARAMETRAGE_SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def obtenir(cls) -> "Parametrage":
        """Retourne le singleton, le crée avec les valeurs par défaut si absent."""
        obj, _ = cls.objects.get_or_create(id=PARAMETRAGE_SINGLETON_ID)
        return obj


# ─── Compteur de numérotation thread-safe ─────────────────────────────────────


class TypeCompteur(models.TextChoices):
    VENTE       = "vente",       "Vente"
    BON_COMMANDE = "bon_commande", "Bon de commande"


class CompteurNumerotation(models.Model):
    """
    Compteur séquentiel par (type, année) permettant une numérotation
    strictement croissante et sans collision sous charge concurrente.

    Utilisation :
        avec transaction.atomic() :
            ligne = CompteurNumerotation.objects \\
                        .select_for_update() \\
                        .get_or_create(type=TypeCompteur.VENTE, annee=annee)[0]
            ligne.sequence += 1
            ligne.save(update_fields=["sequence"])
            numero = appliquer_format(gabarit, annee, ligne.sequence)

    Le verrou SELECT FOR UPDATE garantit qu'une seule transaction obtient
    la même valeur de séquence, éliminant la race condition sur Max()/count().
    """

    type    = models.CharField(max_length=20, choices=TypeCompteur.choices)
    annee   = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        app_label       = "parametrage"
        db_table        = "parametrage_compteur_numerotation"
        unique_together = (("type", "annee"),)
        verbose_name    = "Compteur de numérotation"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.type}/{self.annee} → {self.sequence}"


def appliquer_format_numero(gabarit: str, annee: int, mois: int, seq: int) -> str:
    """
    Applique le gabarit de numérotation configurable.

    Jetons reconnus :
        {YYYY}   → année sur 4 chiffres   (ex: 2026)
        {YY}     → année sur 2 chiffres   (ex: 26)
        {MM}     → mois sur 2 chiffres    (ex: 07)
        {NNNN}   → séquence sur 4 chiffres
        {NNNNN}  → séquence sur 5 chiffres
        {NNNNNN} → séquence sur 6 chiffres
    """
    return (
        gabarit
        .replace("{YYYY}",   str(annee))
        .replace("{YY}",     str(annee)[-2:])
        .replace("{MM}",     f"{mois:02d}")
        .replace("{NNNNNN}", f"{seq:06d}")
        .replace("{NNNNN}",  f"{seq:05d}")
        .replace("{NNNN}",   f"{seq:04d}")
    )


# ── Enregistrement du modèle de paramétrage cloud ────────────────────────────
# models_cloud.py déclare OfficineParametrage ; il doit être importé ici pour que
# Django enregistre le modèle dans l'app « parametrage » (sinon l'état des
# migrations diverge du code).
from gestion.parametrage.models_cloud import OfficineParametrage  # noqa: E402,F401
