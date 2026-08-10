"""
Module : infrastructure/outbox/modeles.py
Description : Modèle Django pour le pattern Outbox transactionnel.

Principe du pattern Outbox :
    Toute modification importante (vente, stock, ordonnance…) est d'abord
    inscrite dans la table outbox_entrees DANS LA MÊME TRANSACTION que la
    modification elle-même. Un processeur Celery indépendant lit et traite
    les entrées en attente.

    Garantie : si la transaction réussit → l'entrée Outbox est créée.
               Si la transaction échoue → aucune entrée Outbox (rollback).

    Cycle de vie :
        EN_ATTENTE → EN_COURS → TRAITE
                               ↘ ECHEC (max_tentatives atteint)

Architecture :
    Service métier
        ↓  (même transaction atomique)
    EntreeOutbox.creer(...)
        ↓  (tâche Celery périodique)
    ProcesseurOutbox.traiter_lot()
        ↓
    EvenementSynchronisation (envoi vers le cloud)
"""

import uuid
from enum import Enum

from django.db import models
from django.utils import timezone


class StatutOutbox(str, Enum):
    """Statuts possibles d'une entrée dans l'Outbox."""
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    TRAITE = "traite"
    ECHEC = "echec"


class EntreeOutbox(models.Model):
    """
    Entrée dans la table Outbox transactionnelle.

    SECURITE : cette table ne peut être créée qu'à l'intérieur d'une
    transaction atomique, garantissant la cohérence avec la modification
    métier associée.

    Champs clés :
    - type_evenement : discriminant permettant au processeur de router
    - charge_utile   : données JSON complètes de l'événement
    - statut         : cycle de vie de l'entrée
    - nombre_tentatives / max_tentatives : logique de rejeu
    - prochaine_tentative : backoff exponentiel
    """

    STATUTS = [
        (StatutOutbox.EN_ATTENTE, "En attente"),
        (StatutOutbox.EN_COURS, "En cours de traitement"),
        (StatutOutbox.TRAITE, "Traité avec succès"),
        (StatutOutbox.ECHEC, "Échec définitif"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identifiant",
    )
    type_evenement = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Type d'événement",
        help_text="Nom de la classe d'événement (ex. : 'EvenementVenteCreee').",
    )
    charge_utile = models.JSONField(
        verbose_name="Charge utile",
        help_text="Données complètes de l'événement sérialisées en JSON.",
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUTS,
        default=StatutOutbox.EN_ATTENTE,
        db_index=True,
        verbose_name="Statut",
    )
    nombre_tentatives = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Nombre de tentatives",
    )
    max_tentatives = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Maximum de tentatives",
    )
    prochaine_tentative = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Prochaine tentative",
        help_text="Timestamp UTC de la prochaine tentative (backoff exponentiel).",
    )
    erreur_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur",
        help_text="Dernière erreur enregistrée lors du traitement.",
    )
    # ─── Traçabilité ───────────────────────────────────────────────────────────
    id_objet = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Identifiant objet source",
        help_text="UUID de l'objet métier ayant généré cet événement.",
    )
    modele_source = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Modèle source",
        help_text="Nom du modèle Django source (ex. : 'Vente').",
    )
    id_utilisateur = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Utilisateur déclencheur",
    )
    cree_le = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Créé le",
    )
    traite_le = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Traité le",
    )

    class Meta:
        app_label = "outbox"
        db_table = "outbox_entrees"
        verbose_name = "Entrée Outbox"
        verbose_name_plural = "Entrées Outbox"
        ordering = ["cree_le"]
        indexes = [
            models.Index(
                fields=["statut", "prochaine_tentative"],
                name="idx_outbox_a_traiter",
            ),
        ]

    def __str__(self) -> str:
        # StatutOutbox est un str-Enum ; en Python 3.11+ f-string utilise le nom de l'enum.
        # On force la valeur brute pour garantir "en_attente" dans la repr.
        statut = self.statut.value if hasattr(self.statut, "value") else str(self.statut)
        return f"[{statut}] {self.type_evenement} — {self.cree_le:%d/%m/%Y %H:%M}"

    # ─── Méthodes de classe ────────────────────────────────────────────────────

    @classmethod
    def creer(
        cls,
        type_evenement: str,
        charge_utile: dict,
        id_objet: uuid.UUID | None = None,
        modele_source: str = "",
        id_utilisateur: uuid.UUID | None = None,
        max_tentatives: int = 5,
    ) -> "EntreeOutbox":
        """
        Crée une entrée Outbox dans la transaction courante.

        Cette méthode DOIT être appelée à l'intérieur d'un bloc
        transaction.atomic() pour garantir la cohérence.

        Args:
            type_evenement: Nom de la classe d'événement.
            charge_utile: Données JSON de l'événement.
            id_objet: UUID de l'objet source (vente, lot, client…).
            modele_source: Nom du modèle Django (ex. : 'Vente').
            id_utilisateur: UUID de l'utilisateur ayant déclenché l'événement.
            max_tentatives: Nombre maximum de tentatives avant ECHEC définitif.

        Returns:
            Instance EntreeOutbox créée.
        """
        return cls.objects.create(
            type_evenement=type_evenement,
            charge_utile=charge_utile,
            id_objet=id_objet,
            modele_source=modele_source,
            id_utilisateur=id_utilisateur,
            max_tentatives=max_tentatives,
            statut=StatutOutbox.EN_ATTENTE,
            prochaine_tentative=timezone.now(),
        )

    @classmethod
    def en_attente(cls):
        """Retourne les entrées prêtes à être traitées."""
        from django.db.models import Q
        # `prochaine_tentative` est NULL tant qu'aucun échec n'a planifié de
        # retry : ces entrées sont immédiatement éligibles. Le filtre strict
        # `__lte` les excluait, laissant les nouvelles entrées jamais traitées.
        return cls.objects.filter(
            Q(prochaine_tentative__isnull=True)
            | Q(prochaine_tentative__lte=timezone.now()),
            statut=StatutOutbox.EN_ATTENTE,
        ).order_by("cree_le")

    # ─── Méthodes d'instance ───────────────────────────────────────────────────

    def marquer_en_cours(self) -> None:
        """Marque l'entrée comme en cours de traitement."""
        self.statut = StatutOutbox.EN_COURS
        self.nombre_tentatives += 1
        self.save(update_fields=["statut", "nombre_tentatives"])

    def marquer_traite(self) -> None:
        """Marque l'entrée comme traitée avec succès."""
        self.statut = StatutOutbox.TRAITE
        self.traite_le = timezone.now()
        self.save(update_fields=["statut", "traite_le"])

    def marquer_echec(self, message_erreur: str, force_definitif: bool = False) -> None:
        """
        Enregistre un échec et planifie la prochaine tentative
        avec un backoff exponentiel (2ⁿ minutes, max 60 min).
        Après max_tentatives, passe au statut ECHEC définitif.

        Args:
            message_erreur: Description de l'erreur survenue.
            force_definitif: Si True, passe immédiatement au statut ECHEC
                sans planifier de retry. À utiliser pour les erreurs métier
                non rejouables (ValueError, données invalides, règle métier…).
                CORRECTION Q2 : sans ce paramètre, une ValueError planifiait
                4 retries inutiles avant d'atteindre ECHEC définitif.
        """
        self.erreur_message = message_erreur

        if force_definitif or self.nombre_tentatives >= self.max_tentatives:
            self.statut = StatutOutbox.ECHEC
            self.prochaine_tentative = None
        else:
            import datetime
            # Backoff exponentiel : 1min, 2min, 4min, 8min, 16min, 32min… max 60min
            delai_minutes = min(2 ** self.nombre_tentatives, 60)
            self.statut = StatutOutbox.EN_ATTENTE
            self.prochaine_tentative = timezone.now() + datetime.timedelta(
                minutes=delai_minutes
            )

        self.save(update_fields=["statut", "erreur_message", "prochaine_tentative"])

    @property
    def peut_etre_rejoue(self) -> bool:
        """Indique si l'entrée peut être rejouée manuellement."""
        return self.statut == StatutOutbox.ECHEC

    def rejouer(self) -> None:
        """Remet l'entrée en file d'attente pour un traitement manuel."""
        if not self.peut_etre_rejoue:
            raise ValueError(
                f"Impossible de rejouer une entrée au statut '{self.statut}'."
            )
        self.statut = StatutOutbox.EN_ATTENTE
        self.nombre_tentatives = 0
        self.prochaine_tentative = timezone.now()
        self.erreur_message = ""
        self.save(update_fields=[
            "statut", "nombre_tentatives", "prochaine_tentative", "erreur_message"
        ])
