"""
Module : infrastructure/repositories/audit.py
Description : Repository pour le journal d'audit immuable.

SECURITE :
    - Aucune méthode de mise à jour ou de suppression n'est exposée.
    - Le journal est append-only : chaque entrée est créée et ne peut plus être modifiée.
    - L'intégrité de chaque entrée est protégée par une empreinte SHA-256.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from .base import DepotAbstrait


class DepotJournalAudit(DepotAbstrait):
    """
    Repository en lecture et ajout uniquement pour le journal d'audit.

    SECURITE :
        - sauvegarder() → création uniquement (jamais de UPDATE)
        - supprimer()   → toujours interdit (lève NotImplementedError)
        - lister()      → lecture filtrée
        - verifier_integrite() → vérification de toutes les empreintes
    """

    def trouver_par_id(self, id: uuid.UUID):
        """Retourne une entrée du journal ou None."""
        from gestion.audit.modeles import JournalAudit
        return JournalAudit.objects.select_related("utilisateur").filter(id=id).first()

    def sauvegarder(self, entite) -> object:
        """
        Crée une entrée dans le journal d'audit (append-only).

        SECURITE : n'effectue jamais de UPDATE — uniquement INSERT.
        """
        if entite.pk and self.existe(entite.pk):
            raise PermissionError(
                "SECURITE : le journal d'audit est immuable. "
                "Toute tentative de modification est interdite et journalisée."
            )
        entite.save()
        return entite

    def supprimer(self, id: uuid.UUID) -> bool:
        """Suppression TOUJOURS INTERDITE pour le journal d'audit."""
        raise NotImplementedError(
            "SECURITE : le journal d'audit est immuable — "
            "la suppression d'entrées est strictement interdite. "
            "Toute tentative constitue une violation de l'audit trail."
        )

    def lister(
        self,
        type_action: Optional[str] = None,
        severite: Optional[str] = None,
        utilisateur_id: Optional[uuid.UUID] = None,
        objet_type: Optional[str] = None,
        date_debut: Optional[datetime] = None,
        date_fin: Optional[datetime] = None,
        limite: int = 500,
    ) -> list:
        """Retourne les entrées du journal avec filtres, triées par date décroissante."""
        from gestion.audit.modeles import JournalAudit

        qs = JournalAudit.objects.select_related("utilisateur").order_by("-cree_le")
        if type_action:
            qs = qs.filter(type_action=type_action)
        if severite:
            qs = qs.filter(severite=severite)
        if utilisateur_id:
            qs = qs.filter(utilisateur_id=utilisateur_id)
        if objet_type:
            qs = qs.filter(objet_type=objet_type)
        if date_debut:
            qs = qs.filter(cree_le__gte=date_debut)
        if date_fin:
            qs = qs.filter(cree_le__lte=date_fin)
        return list(qs[:limite])

    def journaliser(
        self,
        type_action: str,
        description: str,
        utilisateur=None,
        objet: Any = None,
        severite: str = "info",
        adresse_ip: str = "",
        donnees_supplementaires: Optional[dict] = None,
    ) -> object:
        """
        Crée une entrée dans le journal d'audit avec empreinte SHA-256.

        Args:
            type_action: Catégorie de l'action (vente_creee, connexion, …).
            description: Description lisible de l'action.
            utilisateur: UtilisateurPharmacien ayant réalisé l'action.
            objet: Objet Django concerné par l'action (Vente, Client, …).
            severite: Niveau de gravité (info, avertissement, alerte, critique).
            adresse_ip: Adresse IP de la requête.
            donnees_supplementaires: Données JSON additionnelles.

        Returns:
            Instance JournalAudit créée.
        """
        from gestion.audit.modeles import JournalAudit
        return JournalAudit.objects.journaliser(
            type_action=type_action,
            description=description,
            utilisateur=utilisateur,
            objet=objet,
            severite=severite,
            adresse_ip=adresse_ip,
            donnees_supplementaires=donnees_supplementaires or {},
        )

    def verifier_integrite(self) -> dict:
        """
        Vérifie l'empreinte SHA-256 de toutes les entrées du journal.

        Returns:
            {"total": int, "valides": int, "corrompues": list[str (ids)]}
        """
        from gestion.audit.modeles import JournalAudit

        total = 0
        corrompues = []
        for entree in JournalAudit.objects.all():
            total += 1
            try:
                if not entree.verifier_integrite():
                    corrompues.append(str(entree.id))
            except Exception:
                corrompues.append(str(entree.id))

        return {
            "total": total,
            "valides": total - len(corrompues),
            "corrompues": corrompues,
            "integrite_ok": len(corrompues) == 0,
        }
