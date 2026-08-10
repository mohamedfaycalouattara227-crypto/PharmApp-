"""Fiches clients : merge champ par champ + alerte titulaire si divergence sensible."""

from typing import Any, Dict, Optional

from .base import DecisionConflit, ResultatConflit


CHAMPS_SENSIBLES = {"nom", "telephone", "adresse", "plafond_credit", "encours_credit"}


class StrategieClients:
    """
    Règle §2.5 : Fusion champ par champ.
    - Champ vide local & non vide cloud → prendre le cloud.
    - Champ non vide des deux côtés & divergents → prendre local, journaliser
      et lever une alerte titulaire pour les champs sensibles.
    """

    nom = "clients_merge_champ"

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        divergents = []
        fusion: Dict[str, Any] = {}
        cles = set(donnees_locales) | set(donnees_cloud)
        for cle in cles:
            v_local = donnees_locales.get(cle)
            v_cloud = donnees_cloud.get(cle)
            if v_local in (None, "", 0) and v_cloud not in (None, "", 0):
                fusion[cle] = v_cloud
            elif v_cloud in (None, "", 0) and v_local not in (None, "", 0):
                fusion[cle] = v_local
            elif v_local == v_cloud:
                fusion[cle] = v_local
            else:
                fusion[cle] = v_local
                divergents.append(cle)

        alerte = any(c in CHAMPS_SENSIBLES for c in divergents)
        return ResultatConflit(
            decision=DecisionConflit.FUSIONNER,
            payload_final=fusion,
            strategie=self.nom,
            raison=(
                "Fusion champ par champ."
                + (f" Divergences : {', '.join(divergents)}." if divergents else "")
            ),
            champs_divergents=divergents,
            alerte_titulaire=alerte,
        )
