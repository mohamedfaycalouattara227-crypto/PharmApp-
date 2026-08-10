"""
Module : infrastructure/repositories/base.py
Description : Classe abstraite de base pour tous les repositories PharmApp.

Pattern Repository :
    Interface → API (DRF Vues)
        ↓
    Services Métier (logique pure, testable sans DB)
        ↓
    Repository (abstraction de l'accès aux données)
        ↓
    Django ORM → PostgreSQL

Avantages :
    - Les services n'importent plus jamais de modèles Django directement.
    - On peut substituer le backend de données (PostgreSQL → SQLite en test)
      sans modifier une seule ligne de service.
    - Les tests unitaires mockent uniquement le repository, pas l'ORM entier.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")  # Type de l'entité gérée par le repository


class DepotAbstrait(ABC, Generic[T]):
    """
    Classe de base abstraite pour tous les repositories PharmApp.

    Chaque repository concret hérite de cette classe et implémente
    les méthodes d'accès aux données pour un modèle Django donné.

    Convention de nommage :
        - Méthodes en français : trouver_par_id, sauvegarder, supprimer…
        - Pas de logique métier dans les repositories — uniquement l'accès aux données.
        - Pas d'appels directs au bus d'événements depuis un repository.
    """

    # ─── Opérations de base (CRUD) ────────────────────────────────────────────

    @abstractmethod
    def trouver_par_id(self, id: uuid.UUID) -> Optional[T]:
        """
        Recherche une entité par son identifiant UUID.

        Args:
            id: UUID de l'entité.

        Returns:
            L'entité si elle existe, None sinon.
        """
        raise NotImplementedError

    @abstractmethod
    def sauvegarder(self, entite: T) -> T:
        """
        Sauvegarde (crée ou met à jour) une entité.

        Args:
            entite: Instance de l'entité à sauvegarder.

        Returns:
            L'entité sauvegardée (avec l'id généré si nouvelle).
        """
        raise NotImplementedError

    @abstractmethod
    def supprimer(self, id: uuid.UUID) -> bool:
        """
        Supprime logiquement une entité (soft delete — jamais de DELETE SQL).

        Args:
            id: UUID de l'entité à désactiver.

        Returns:
            True si l'entité existait et a été désactivée, False sinon.
        """
        raise NotImplementedError

    @abstractmethod
    def lister(self, **filtres: Any) -> list[T]:
        """
        Retourne une liste d'entités filtrées selon les critères fournis.

        Args:
            **filtres: Critères de filtrage spécifiques au repository.

        Returns:
            Liste d'entités correspondant aux critères.
        """
        raise NotImplementedError

    # ─── Méthodes utilitaires ─────────────────────────────────────────────────

    def existe(self, id: uuid.UUID) -> bool:
        """Vérifie si une entité avec cet identifiant existe."""
        return self.trouver_par_id(id) is not None

    def trouver_ou_erreur(self, id: uuid.UUID, message: str = "") -> T:
        """
        Recherche une entité ou lève une ValueError.

        Args:
            id: UUID de l'entité.
            message: Message d'erreur personnalisé.

        Returns:
            L'entité trouvée.

        Raises:
            ValueError: si l'entité n'existe pas.
        """
        entite = self.trouver_par_id(id)
        if entite is None:
            raise ValueError(
                message or f"Entité introuvable (ID : {id})."
            )
        return entite
