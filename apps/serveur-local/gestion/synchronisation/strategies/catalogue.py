"""
Stratégie de résolution de conflit — Catalogue.

CORRECTION AUDIT v2 — Séparation des règles par type de champ :

  Le CdC §2.5 distingue deux sous-règles pour le catalogue :
    a) Prix de vente  → last-writer-wins horodaté (LWW) — les deux sites
       peuvent légitimement modifier le prix ; on retient le plus récent.
    b) Fiche produit (nom, DCI, dosage, forme, catégorie, code, etc.)
       → cloud autoritaire + validation obligatoire avant application locale.
       Le cloud est le référentiel central du catalogue pharmaceutique ;
       un changement de nom ou de dosage d'un médicament ne doit pas être
       écrasé silencieusement par une modification locale.

  L'implémentation originale appliquait LWW uniformément à tous les champs,
  ce qui permettait à une modification locale d'un nom de médicament
  d'écraser silencieusement la version cloud — non conforme au CdC.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import DecisionConflit, ResultatConflit

# Champs soumis au LWW (prix, conditions commerciales modifiables en local)
CHAMPS_LWW = frozenset({
    "prix_vente",
    "prix_achat_unitaire",
    "taux_tva",
    "prix_minimum_vente",
})

# Champs de la fiche produit → cloud autoritaire
CHAMPS_FICHE_PRODUIT = frozenset({
    "nom",
    "dci",
    "dosage",
    "forme",
    "code",
    "code_barre",
    "categorie",
    "categorie_id",
    "necessite_ordonnance",
    "necessite_tracabilite_lot",
    "classe_therapeutique",
    "voie_administration",
    "conditionnement",
    "description",
})


def _parse(dt: Any) -> Optional[datetime]:
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _champs_divergents(locales: Dict[str, Any], cloud: Dict[str, Any]) -> List[str]:
    """Retourne la liste des champs dont la valeur diffère."""
    tous = set(locales.keys()) | set(cloud.keys())
    return [c for c in tous if locales.get(c) != cloud.get(c)]


class StrategieCatalogue:
    """
    Règle §2.5 — Catalogue, deux sous-règles :
      • Prix       : last-writer-wins horodaté (modifie_le).
      • Fiche      : cloud autoritaire + champs divergents tracés pour validation.

    Si les données divergent à la fois sur la fiche ET sur le prix, la stratégie
    applique la règle fiche (cloud autoritaire) sur l'ensemble : la divergence de
    fiche est plus critique et doit rester traçable comme un tout.
    """

    nom = "catalogue_lww"

    def resoudre(
        self,
        donnees_locales: Dict[str, Any],
        donnees_cloud: Dict[str, Any],
        contexte: Optional[Dict[str, Any]] = None,
    ) -> ResultatConflit:
        divergents = _champs_divergents(donnees_locales, donnees_cloud)

        # ── Vérification : la fiche produit diverge-t-elle ? ─────────────────
        fiche_diverge = any(c in CHAMPS_FICHE_PRODUIT for c in divergents)
        prix_diverge  = any(c in CHAMPS_LWW for c in divergents)

        if fiche_diverge:
            # Règle fiche : cloud autoritaire.
            # Les champs divergents sont listés pour validation éventuelle.
            champs_fiche_divergents = [c for c in divergents if c in CHAMPS_FICHE_PRODUIT]
            return ResultatConflit(
                decision=DecisionConflit.APPLIQUER_CLOUD,
                payload_final=donnees_cloud,
                strategie=self.nom,
                raison=(
                    "Fiche produit modifiée côté cloud — version cloud appliquée "
                    "(CdC §2.5 : cloud autoritaire pour nom/dosage/catégorie). "
                    f"Champs impactés : {', '.join(champs_fiche_divergents)}."
                ),
                champs_divergents=champs_fiche_divergents,
                alerte_titulaire=len(champs_fiche_divergents) > 0,
            )

        if prix_diverge:
            # Règle prix : last-writer-wins horodaté.
            ts_local = _parse(donnees_locales.get("modifie_le"))
            ts_cloud  = _parse(donnees_cloud.get("modifie_le"))

            if ts_local and ts_cloud and ts_local > ts_cloud:
                return ResultatConflit(
                    decision=DecisionConflit.CONSERVER_LOCAL,
                    payload_final=donnees_locales,
                    strategie=self.nom,
                    raison=(
                        f"Prix local plus récent ({ts_local.isoformat()}) — "
                        "last-writer-wins : version locale conservée."
                    ),
                    champs_divergents=[c for c in divergents if c in CHAMPS_LWW],
                )

            return ResultatConflit(
                decision=DecisionConflit.APPLIQUER_CLOUD,
                payload_final=donnees_cloud,
                strategie=self.nom,
                raison=(
                    "Prix : last-writer-wins — version cloud appliquée. "
                    f"cloud={ts_cloud}, local={ts_local}."
                ),
                champs_divergents=[c for c in divergents if c in CHAMPS_LWW],
            )

        # Aucune divergence sur les champs connus → cloud par sécurité
        return ResultatConflit(
            decision=DecisionConflit.APPLIQUER_CLOUD,
            payload_final=donnees_cloud,
            strategie=self.nom,
            raison="Aucune divergence sur les champs gérés — version cloud appliquée par défaut.",
        )
