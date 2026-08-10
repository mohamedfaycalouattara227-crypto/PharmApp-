"""
gestion/produits_controles/models.py
Registre réglementaire des stupéfiants et psychotropes.
Chaque mouvement est journalisé de manière CRITIQUE dans l'audit.
"""

import uuid
from django.conf import settings
from django.db import models


class TypeMouvementControle(models.TextChoices):
    ENTREE          = "entree",          "Entrée (réception)"
    SORTIE_VENTE    = "sortie_vente",    "Sortie (vente sur ordonnance)"
    RETOUR          = "retour",          "Retour fournisseur"
    MISE_AU_REBUT   = "mise_au_rebut",   "Mise au rebut (périmé)"
    CONTROLE_AUTORITE = "controle_autorite", "Contrôle autorités (inventaire)"


class RegistreProduitControle(models.Model):
    """
    Registre réglementaire des stupéfiants et psychotropes.
    Toute entrée est définitive et traçable (audit CRITIQUE).
    Ce registre est soumis aux inspections de la DGPML (Burkina Faso).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medicament = models.ForeignKey(
        "catalogue.Medicament",
        on_delete=models.PROTECT,
        related_name="registre_controle",
        limit_choices_to={"est_produit_controle": True},
    )
    lot = models.ForeignKey(
        "catalogue.Lot",
        on_delete=models.PROTECT,
        related_name="registre_controle",
    )
    numero_lot_fabricant = models.CharField(max_length=100)
    type_mouvement = models.CharField(
        max_length=25, choices=TypeMouvementControle.choices
    )

    quantite_mouvement = models.PositiveIntegerField()
    unite = models.CharField(max_length=50, verbose_name="Unité (ampoules, comprimés…)")
    stock_avant = models.PositiveIntegerField()
    stock_apres = models.PositiveIntegerField()

    # Références légales obligatoires
    ordonnance = models.ForeignKey(
        "ordonnances.Ordonnance",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="mouvements_controles",
        verbose_name="Ordonnance sécurisée",
    )
    prescripteur_nom = models.CharField(max_length=200, blank=True)
    prescripteur_num_ordre = models.CharField(
        max_length=50, blank=True, verbose_name="N° d'ordre du médecin"
    )
    # Nom patient — chiffré AES-256-GCM avec la clé
    # ``settings.ORDONNANCE_ENCRYPTION_KEY`` (voir
    # ``gestion.produits_controles.chiffrement``).
    # On expose ``patient_nom`` en lecture/écriture via une propriété
    # Python : le code applicatif continue de manipuler du texte clair,
    # la base ne contient que le blob chiffré (``patient_nom_chiffre``).
    patient_nom_chiffre = models.TextField(
        blank=True, default="",
        verbose_name="Nom patient (chiffré AES-256-GCM, base64)",
    )
    numero_registre_national = models.CharField(
        max_length=50, blank=True,
        verbose_name="N° de registre national réglementaire",
    )

    effectue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mouvements_controles",
        verbose_name="Pharmacien responsable",
    )
    supervise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="supervisions_controles",
        verbose_name="Superviseur (titulaire)",
    )

    motif = models.TextField(blank=True)
    notes_reglementaires = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    # Lien vers la ligne de vente d'origine — permet au job de réconciliation
    # (infrastructure.taches_celery.reconcilier_registre_produits_controles)
    # de détecter, par simple filtre isnull, les ventes de produits contrôlés
    # dépourvues d'entrée registre correspondante.
    ligne_vente = models.OneToOneField(
        "ventes.LigneVente",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="entree_registre_controle",
        verbose_name="Ligne de vente d'origine",
    )
    # True si cette entrée a été créée après coup par le job de réconciliation
    # (l'écriture initiale, faite pendant la vente, avait échoué) plutôt que
    # pendant le flux de vente normal. Distinction visible à l'export DGPML.
    cree_par_reconciliation = models.BooleanField(default=False)

    class Meta:
        db_table = "produits_controles_registre"
        verbose_name = "Registre produit contrôlé"
        verbose_name_plural = "Registre produits contrôlés"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["medicament", "cree_le"]),
            models.Index(fields=["type_mouvement", "cree_le"]),
        ]

    def __str__(self):
        return (
            f"[{self.get_type_mouvement_display()}] "
            f"{self.medicament.nom} × {self.quantite_mouvement} {self.unite} "
            f"— {self.cree_le.date()}"
        )

    # ─── Nom patient : accès en clair, stockage chiffré ─────────────────
    @property
    def patient_nom(self) -> str:
        """Retourne le nom patient déchiffré (ou "" si non renseigné)."""
        from gestion.produits_controles.chiffrement import dechiffrer_nom_patient
        return dechiffrer_nom_patient(self.patient_nom_chiffre or "")

    @patient_nom.setter
    def patient_nom(self, valeur: str) -> None:
        from gestion.produits_controles.chiffrement import chiffrer_nom_patient
        self.patient_nom_chiffre = chiffrer_nom_patient(valeur or "")

    # ─── Immuabilité réglementaire — défense en profondeur ───────────────────
    # Ces surcharges constituent la DEUXIÈME couche de protection (après les
    # HTTP 405 dans VueProduitControle), couvrant les accès hors API :
    # shell Django, commandes d'administration, scripts de migration, tests.
    # Elles garantissent qu'aucun chemin de code ne peut silencieusement altérer
    # ou supprimer un enregistrement réglementaire, quelle que soit l'origine
    # de l'appel.

    def save(self, *args, **kwargs):
        """
        Création autorisée, toute modification ultérieure interdite.

        Raises:
            PermissionDenied: Si une tentative de modification d'une entrée
                existante est détectée (``self.pk`` déjà valorisé).
        """
        # NB : la PK est un UUID généré côté Python (``default=uuid4``) : elle
        # est déjà valorisée AVANT l'INSERT. Seul ``_state.adding`` distingue
        # de manière fiable une création d'une modification.
        if not self._state.adding:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(
                "Le registre des produits contrôlés est immuable — "
                "toute modification d'une entrée existante est interdite "
                "(obligation légale de traçabilité, réf. ANRP/DGPML)."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Suppression physique interdite — obligation réglementaire de traçabilité.

        Raises:
            PermissionDenied: Toujours. Aucune suppression n'est jamais autorisée.
        """
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "La suppression d'une entrée du registre des produits contrôlés est "
            "interdite (obligation légale de traçabilité, réf. ANRP/DGPML). "
            "Pour signaler une erreur, contactez le pharmacien titulaire."
        )
