"""
Stratégie de résolution de conflit — Ventes.

CORRECTION AUDIT v2 — Inversion de la règle §2.5 :
  Le CdC §2.5 stipule : « la vente locale est définitive et immuable,
  le cloud ne fait qu'archiver ». L'implémentation originale appliquait
  systématiquement APPLIQUER_CLOUD, ce qui est l'inverse exact du cahier
  des charges. Sur un système de caisse, une résolution de conflit qui
  peut réécrire une vente locale avec une version cloud est un risque
  financier direct.

Règle corrigée :
  - Cas normal    → CONSERVER_LOCAL (la caisse est la source de vérité)
  - Cas particulier : annulation cloud non répliquée localement
                  → APPLIQUER_CLOUD avec alerte titulaire (annulation légitime
                    décidée par un superviseur — doit être propagée)

La logique d'archivage cloud (sync ascendante) est gérée par le processeur
outbox, pas par cette stratégie de résolution descendante.
"""

from typing import Any, Dict, Optional

from .base import DecisionConflit, ResultatConflit


class StrategieVentesImmuable:
    """
    Règle §2.5 : Une vente locale déjà enregistrée est définitive et immuable.
    Le cloud archive ; il ne réécrit pas.

    Exception unique : annulation cloud non répliquée (ex. annulation saisie
    directement en back-office par un titulaire) — propagée localement avec
    alerte pour traçabilité financière.
    """

    nom = "ventes_immuable"

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        # Cas particulier : annulation cloud d'une vente validée localement.
        # C'est une décision de gestion (titulaire / superviseur) qui doit
        # être propagée malgré l'immuabilité — mais avec alerte obligatoire.
        if (
            donnees_cloud.get("statut") == "annulee"
            and donnees_locales.get("statut") == "validee"
        ):
            return ResultatConflit(
                decision=DecisionConflit.APPLIQUER_CLOUD,
                payload_final=donnees_cloud,
                strategie=self.nom,
                raison=(
                    "Annulation cloud propagée localement : vente annulée côté cloud "
                    "(décision superviseur). Alerte titulaire générée pour audit financier."
                ),
                alerte_titulaire=True,
            )

        # Cas général : vente locale → CONSERVER_LOCAL (cahier des charges §2.5).
        # La version cloud est enregistrée dans le journal de conflit pour audit,
        # mais n'écrase pas la vente locale.
        return ResultatConflit(
            decision=DecisionConflit.CONSERVER_LOCAL,
            payload_final=donnees_locales,
            strategie=self.nom,
            raison=(
                "Vente locale immuable conservée (CdC §2.5) : "
                "la caisse est la source de vérité pour les ventes. "
                "La version cloud est archivée en journal de conflit."
            ),
        )
