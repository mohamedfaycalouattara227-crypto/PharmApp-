"""Stock : merge additif via deltas (CRDT compteur)."""

from decimal import Decimal
from typing import Any, Dict, Optional

from .base import DecisionConflit, ResultatConflit


class StrategieStockAdditif:
    """
    Règle §2.5 : Le stock est un compteur. Deux nœuds qui décrémentent en
    parallèle ne doivent pas s'écraser ; on additionne les *deltas* signés
    depuis la dernière synchronisation réussie.

    Contrat d'entrée :
      donnees_locales / donnees_cloud contiennent :
        - `quantite_disponible` : entier
        - `delta_depuis_sync`   : entier signé (mouvements accumulés localement)
    """

    nom = "stock_additif"

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        base_commune = int(contexte.get("quantite_base_commune", 0)) if contexte else 0
        delta_local = int(donnees_locales.get("delta_depuis_sync", 0))
        delta_cloud = int(donnees_cloud.get("delta_depuis_sync", 0))

        quantite_fusionnee = base_commune + delta_local + delta_cloud
        if quantite_fusionnee < 0:
            # Sur-consommation croisée : on escalade vers le titulaire
            return ResultatConflit(
                decision=DecisionConflit.ESCALADER,
                payload_final={
                    **donnees_cloud,
                    "quantite_disponible": 0,
                    "sur_consommation": quantite_fusionnee,
                },
                strategie=self.nom,
                raison=(
                    f"Sur-consommation détectée : base={base_commune}, "
                    f"delta_local={delta_local}, delta_cloud={delta_cloud}."
                ),
                alerte_titulaire=True,
            )
        payload = {
            **donnees_cloud,
            "quantite_disponible": quantite_fusionnee,
            "delta_depuis_sync": 0,
        }
        return ResultatConflit(
            decision=DecisionConflit.FUSIONNER,
            payload_final=payload,
            strategie=self.nom,
            raison=(
                f"Fusion additive : {base_commune} + ({delta_local}) + ({delta_cloud}) "
                f"= {quantite_fusionnee}."
            ),
        )
