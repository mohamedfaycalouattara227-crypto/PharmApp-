"""
gestion/synchronisation/models.py
Modèles de synchronisation locale ↔ cloud.
Architecture local-first : toutes les opérations fonctionnent hors ligne.
"""

import uuid
from django.db import models
from django.utils import timezone


class StatutConnexion(models.TextChoices):
    EN_LIGNE  = "en_ligne",  "En ligne"
    HORS_LIGNE = "hors_ligne", "Hors ligne"
    DEGRADEE  = "degradee",  "Connexion dégradée"


class EtatSynchronisation(models.Model):
    """
    État courant de la synchronisation — SINGLETON.

    CORRECTION Q1 : Sans contrainte d'unicité, deux tâches Celery concurrentes
    pouvaient chacune créer une ligne distincte. L'état était alors lu de façon
    non déterministe via .order_by("-modifie_le").first().

    Solution retenue : UUID primaire fixe (SINGLETON_ID). La méthode save()
    force toujours cet UUID, rendant toute insertion concurrente une simple
    mise à jour (upsert via l'unicité de la clé primaire). La méthode de
    classe obtenir() encapsule le pattern get_or_create pour l'ensemble du code.
    """

    # UUID fixe garantissant l'unicité au niveau de la clé primaire Django/DB.
    SINGLETON_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statut_connexion = models.CharField(
        max_length=15,
        choices=StatutConnexion.choices,
        default=StatutConnexion.HORS_LIGNE,
    )
    derniere_sync_reussie = models.DateTimeField(null=True, blank=True)
    derniere_tentative = models.DateTimeField(null=True, blank=True)
    nombre_evenements_en_attente = models.PositiveIntegerField(default=0)
    nombre_evenements_en_echec = models.PositiveIntegerField(default=0)
    nombre_conflits_non_resolus = models.PositiveIntegerField(default=0)
    message_statut = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "synchronisation_etat"
        verbose_name = "État de synchronisation"
        verbose_name_plural = "États de synchronisation"
        ordering = ["-modifie_le"]

    def save(self, *args, **kwargs):
        """Force l'UUID singleton — toute instance partage le même enregistrement DB."""
        self.id = self.SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def obtenir(cls) -> "EtatSynchronisation":
        """Retourne (ou crée) le singleton de synchronisation."""
        obj, _ = cls.objects.get_or_create(id=cls.SINGLETON_ID)
        return obj

    def __str__(self):
        return f"Sync {self.statut_connexion} — {self.derniere_sync_reussie or 'Jamais'}"


class StatutConflit(models.TextChoices):
    NON_RESOLU  = "non_resolu",  "Non résolu"
    RESOLU_LOCAL = "resolu_local", "Résolu — version locale conservée"
    RESOLU_CLOUD = "resolu_cloud", "Résolu — version cloud appliquée"
    IGNORE      = "ignore",      "Ignoré"


class ConflitSynchronisation(models.Model):
    """Conflit détecté entre une donnée locale et la version cloud."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    modele = models.CharField(max_length=100, verbose_name="Modèle Django concerné")
    id_objet = models.UUIDField(verbose_name="UUID de l'objet en conflit")
    donnees_locales = models.JSONField(verbose_name="Version locale")
    donnees_cloud = models.JSONField(verbose_name="Version cloud")
    statut = models.CharField(
        max_length=20,
        choices=StatutConflit.choices,
        default=StatutConflit.NON_RESOLU,
    )
    resolu_par = models.CharField(max_length=50, blank=True)
    resolu_le = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "synchronisation_conflit"
        verbose_name = "Conflit de synchronisation"
        verbose_name_plural = "Conflits de synchronisation"
        ordering = ["-cree_le"]
        unique_together = [("modele", "id_objet", "statut")]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["modele", "id_objet"]),
        ]

    def __str__(self):
        return f"Conflit [{self.modele}] {self.id_objet} — {self.get_statut_display()}"


class StatutEvenementSync(models.TextChoices):
    """Cycle de vie d'un événement de synchronisation locale → cloud."""
    EN_ATTENTE = "en_attente", "En attente"
    ENVOYE     = "envoye",     "Envoyé"
    ECHEC      = "echec",      "Échec"


class EvenementSynchronisation(models.Model):
    """
    Journal local des événements métier à propager vers le cloud.

    Alimenté par le ProcesseurOutbox lors du routage : chaque entrée Outbox
    routée produit ici une trace typée (vente_creee, stock_ajuste, …) qui
    survit au nettoyage de l'Outbox et sert de piste d'audit de la
    synchronisation, y compris en mode hors ligne prolongé.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_evenement = models.CharField(max_length=60, verbose_name="Type d'événement")
    modele_source = models.CharField(max_length=60, verbose_name="Modèle source")
    id_objet = models.CharField(max_length=64, verbose_name="Identifiant de l'objet")
    statut = models.CharField(
        max_length=15,
        choices=StatutEvenementSync.choices,
        default=StatutEvenementSync.EN_ATTENTE,
    )
    charge_utile = models.JSONField(default=dict, blank=True)
    envoye_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "synchronisation_evenement"
        verbose_name = "Événement de synchronisation"
        verbose_name_plural = "Événements de synchronisation"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["type_evenement", "statut"]),
            models.Index(fields=["id_objet"]),
        ]

    def __str__(self) -> str:
        return f"{self.type_evenement} ({self.statut})"

    def marquer_envoye(self) -> None:
        self.statut = StatutEvenementSync.ENVOYE
        self.envoye_le = timezone.now()
        self.save(update_fields=["statut", "envoye_le", "modifie_le"])
