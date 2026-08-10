"""
Stratégie de résolution de conflit — Utilisateurs / Rôles.

CORRECTIONS AUDIT v2 :

  1. Inversion de la règle §2.5 :
     Le CdC §2.5 stipule : « local prévaut, avec notification au cloud pour
     audit ». L'implémentation originale appliquait APPLIQUER_CLOUD par défaut
     (cloud autoritaire), ce qui est l'inverse du cahier des charges.
     Règle corrigée → CONSERVER_LOCAL + notification d'audit vers le cloud.

  2. HIERARCHIE_ROLES incomplète :
     L'ancienne liste ne contenait que 5 rôles et utilisait le mauvais libellé
     « pharmacien_assistant » au lieu de « pharmacien_adjoint ». Le modèle réel
     définit 7 rôles (RoleUtilisateur dans gestion.authentification.models).
     Les rôles inconnus retournaient rang=-1, ce qui causait une classification
     erronée en cas de conflit impliquant stagiaire ou pharmacien_adjoint.

  3. Rétrogradation : comportement conservé (ESCALADER + alerte titulaire)
     car une rétrogradation silencieuse reste inacceptable quelle que soit la
     règle de prédominance locale.
"""

from typing import Any, Dict, Optional

from .base import DecisionConflit, ResultatConflit

# Hiérarchie complète — miroir fidèle de HIERARCHIE_ROLES dans
# gestion.authentification.models (7 rôles, noms identiques aux valeurs
# de RoleUtilisateur.TextChoices).
HIERARCHIE_ROLES = [
    "stagiaire",            # 0
    "caissier",             # 1
    "assistant",            # 2
    "gestionnaire_stock",   # 3
    "pharmacien_adjoint",   # 4
    "titulaire",            # 5
    "administrateur",       # 6
]


def _rang(role: Optional[str]) -> int:
    """Retourne le rang hiérarchique d'un rôle, -1 si inconnu."""
    if role is None:
        return -1
    try:
        return HIERARCHIE_ROLES.index(role)
    except ValueError:
        return -1


class StrategieUtilisateurs:
    """
    Règle §2.5 : Local prévaut pour les utilisateurs et rôles,
    avec notification au cloud pour audit.

    Cas particulier : si la version cloud rétrograde un utilisateur
    (rôle inférieur au rôle local), on ESCALADE au titulaire — c'est
    une anomalie à examiner avant toute application (direction ou cloud
    doivent confirmer explicitement).
    """

    nom = "utilisateurs_local_prevaut"

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        rang_local = _rang(donnees_locales.get("role"))
        rang_cloud = _rang(donnees_cloud.get("role"))

        # Cas particulier : rétrogradation cloud détectée.
        # Même avec la règle « local prévaut », une rétrogradation doit être
        # signalée car elle peut indiquer une révocation légitime (pharmacien
        # suspendu, fin de contrat) — ne jamais l'appliquer silencieusement.
        if rang_cloud >= 0 and rang_cloud < rang_local:
            return ResultatConflit(
                decision=DecisionConflit.ESCALADER,
                payload_final=donnees_locales,   # on conserve le local en attendant la validation
                strategie=self.nom,
                raison=(
                    "Rétrogradation cloud détectée : "
                    f"local={donnees_locales.get('role')} (rang {rang_local}), "
                    f"cloud={donnees_cloud.get('role')} (rang {rang_cloud}). "
                    "Validation titulaire requise avant toute application."
                ),
                alerte_titulaire=True,
            )

        # Cas général : local prévaut (CdC §2.5).
        # La divergence est notifiée vers le cloud pour audit trail.
        return ResultatConflit(
            decision=DecisionConflit.CONSERVER_LOCAL,
            payload_final=donnees_locales,
            strategie=self.nom,
            raison=(
                "Version locale conservée (CdC §2.5 : local prévaut pour les utilisateurs). "
                "Divergence notifiée au cloud pour audit."
            ),
        )
