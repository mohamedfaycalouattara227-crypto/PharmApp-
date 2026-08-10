"""
infrastructure/outbox/processeur.py
Processeur Outbox — PharmApp Local.

PHASE 1 — Remplacement de l'accès Supabase direct par l'API Cloud PharmApp :
  - Avant : _envoyer_vers_supabase() utilisait SUPABASE_SERVICE_KEY (clé unique globale)
            → vulnérabilité multi-tenant : un serveur compromis accédait à toutes les pharmacies.
  - Après : _envoyer_vers_cloud() utilise la clé API propre à cette officine
            → isolée, révocable, auditée côté cloud.

Architecture :
  Le processeur envoie chaque événement vers POST /api/cloud/sync/evenements/
  avec le header X-Api-Key: phk_<token_officine>.

  Idempotence : l'UUID de l'EntreeOutbox est transmis → ON CONFLICT DO NOTHING côté cloud.
  Réseau absent → événement reste EN_ATTENTE, backoff exponentiel géré par marquer_echec().
  La pharmacie continue de fonctionner hors-ligne (Principe n°1).
"""

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Optional

from .modeles import EntreeOutbox, StatutOutbox

logger = logging.getLogger("pharmapp.outbox")


class ProcesseurOutbox:
    """
    Processeur de l'Outbox transactionnel de PharmApp.

    Responsabilités :
      - Lire les entrées EN_ATTENTE par lot
      - Router chaque entrée vers le bon gestionnaire local
      - Envoyer vers le Cloud PharmApp via API sécurisée (Phase 1)
      - Enregistrer les succès et les erreurs
      - Gérer le backoff exponentiel en cas d'échec
    """

    TAILLE_LOT: int = 50

    ROUTAGE: dict[str, str] = {
        "EvenementVenteCreee":               "_traiter_vente_creee",
        "EvenementVenteAnnulee":             "_traiter_vente_annulee",
        "EvenementAvoirCree":                "_traiter_avoir_cree",
        "EvenementStockAjuste":              "_traiter_stock_ajuste",
        "EvenementLivraison":                "_traiter_livraison",
        "EvenementAlerteStockBas":           "_traiter_alerte_stock",
        "EvenementOrdonnanceNumerisee":      "_traiter_ordonnance",
        "EvenementConnexion":                "_traiter_connexion",
        "EvenementCompteCree":               "_traiter_compte_cree",
        "EvenementClotureCaisse":            "_traiter_cloture_caisse",
        "EvenementProduitsControlesDelivre": "_traiter_produit_controle",
    }

    # Mapping type d'événement local → type_evenement attendu par l'API cloud
    MAPPING_TYPE_CLOUD: dict[str, str] = {
        "EvenementVenteCreee":               "VENTE_CREEE",
        "EvenementVenteAnnulee":             "VENTE_ANNULEE",
        "EvenementAvoirCree":                "AVOIR_CREE",
        "EvenementStockAjuste":              "STOCK_AJUSTE",
        "EvenementLivraison":                "RECEPTION_LIVRAISON",
        "EvenementAlerteStockBas":           "ALERTE_STOCK",
        "EvenementOrdonnanceNumerisee":      "ORDONNANCE_NUMERISEE",
        "EvenementConnexion":                "CONNEXION",
        "EvenementCompteCree":               "COMPTE_CREE",
        "EvenementClotureCaisse":            "CLOTURE_CAISSE",
        "EvenementProduitsControlesDelivre": "PRODUIT_CONTROLE_DELIVRE",
    }

    def traiter_lot(self, taille: Optional[int] = None) -> dict:
        """
        Traite un lot d'entrées Outbox en attente.

        Returns:
            Rapport : {"traites": int, "echecs": int, "ignores": int, "total": int}
        """
        taille = taille or self.TAILLE_LOT
        entrees = list(EntreeOutbox.en_attente()[:taille])

        rapport = {"traites": 0, "echecs": 0, "ignores": 0, "total": len(entrees)}

        if not entrees:
            logger.debug("Outbox : aucune entrée en attente.")
            return rapport

        logger.info("Outbox : traitement de %d entrée(s).", len(entrees))

        for entree in entrees:
            try:
                entree.marquer_en_cours()

                # Routage local (gestion synchronisation interne)
                self._router_evenement(entree)

                # Envoi vers le Cloud PharmApp (Phase 1 — remplace Supabase direct)
                self._envoyer_vers_cloud(entree)

                entree.marquer_traite()
                rapport["traites"] += 1

            except ValueError as exc:
                entree.marquer_echec(str(exc), force_definitif=True)
                rapport["echecs"] += 1
                logger.warning(
                    "Outbox : erreur métier définitive sur '%s' (id=%s) : %s",
                    entree.type_evenement, entree.id, exc,
                )
            except Exception as exc:
                entree.marquer_echec(str(exc))
                rapport["echecs"] += 1
                logger.error(
                    "Outbox : erreur inattendue sur '%s' (id=%s) : %s",
                    entree.type_evenement, entree.id, exc,
                    exc_info=True,
                )

        logger.info(
            "Outbox : traitement terminé — %d traités, %d échecs.",
            rapport["traites"], rapport["echecs"],
        )
        return rapport

    # ─── Envoi vers le Cloud PharmApp (PHASE 1) ───────────────────────────────

    def _envoyer_vers_cloud(self, entree: EntreeOutbox) -> None:
        """
        Envoie l'événement vers l'API Cloud PharmApp.

        POST {CLOUD_API_URL}/api/cloud/sync/evenements/
        Headers :
          X-Api-Key: phk_<cle_officine>         ← clé propre à cette pharmacie
          X-PharmApp-Version: <version>          ← télémétrie version logiciel
          Content-Type: application/json

        Corps :
          {
            "uuid": "<UUID de l'EntreeOutbox>",
            "type_evenement": "<TYPE_CLOUD>",
            "version_schema": 1,
            "timestamp_local": "<ISO 8601>",
            "charge_utile": { ... }
          }

        Codes retour acceptés :
          201 → nouveau, ingéré avec succès
          409 → déjà connu (idempotence) → considéré comme succès

        Si le cloud est inaccessible → lève RuntimeError → backoff exponentiel.
        Si le cloud n'est pas configuré → mode dégradé silencieux (mode hors-ligne).
        """
        try:
            from gestion.parametrage.services_cloud import ServiceParametrageCloud
            if not ServiceParametrageCloud.est_configure():
                logger.debug(
                    "Outbox : cloud non configuré, événement %s conservé localement.",
                    entree.id,
                )
                return

            config = ServiceParametrageCloud.obtenir_config()
        except Exception as exc:
            # Configuration absente ou corrompue → mode dégradé
            logger.warning(
                "Outbox : impossible de lire la config cloud (%s) — événement %s conservé.",
                exc, entree.id,
            )
            return

        # Construction du payload cloud
        type_cloud = self.MAPPING_TYPE_CLOUD.get(
            entree.type_evenement, entree.type_evenement
        )

        timestamp = (
            entree.cree_le.isoformat()
            if hasattr(entree, "cree_le") and entree.cree_le
            else ""
        )

        payload = {
            "uuid": str(entree.id),
            "type_evenement": type_cloud,
            "version_schema": 1,
            "timestamp_local": timestamp,
            "charge_utile": entree.charge_utile,
        }

        from django.conf import settings
        version_logiciel = getattr(settings, "PHARMAPP_VERSION", "")

        url = f"{config.cloud_api_url}/api/cloud/sync/evenements/"
        donnees = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=donnees,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": config.cle_api,
                "X-PharmApp-Version": version_logiciel,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.status
                # 201 = nouveau, 409 = déjà connu (idempotence) → les deux sont OK
                if status_code not in (200, 201, 409):
                    raise RuntimeError(
                        f"Cloud a répondu {status_code} pour l'événement {entree.id}."
                    )
                if status_code == 409:
                    logger.debug(
                        "Outbox : événement %s déjà connu du cloud (idempotence).",
                        entree.id,
                    )
                else:
                    logger.debug(
                        "Outbox : événement %s envoyé vers le cloud (%s).",
                        entree.id, config.code_officine,
                    )

        except urllib.error.HTTPError as exc:
            # 4xx → erreur définitive (ne pas retenter)
            if 400 <= exc.code < 500:
                raise ValueError(
                    f"Cloud a rejeté l'événement {entree.id} (HTTP {exc.code}) : {exc.reason}"
                )
            raise RuntimeError(
                f"Cloud HTTP {exc.code} pour l'événement {entree.id} : {exc.reason}"
            )
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cloud inaccessible pour l'événement {entree.id} : {exc.reason}"
            )

    # ─── Routage interne ──────────────────────────────────────────────────────

    @classmethod
    def _nom_canonique(cls, type_evenement: str) -> str:
        """Normalise un type d'événement vers sa clé de ROUTAGE.

        Deux conventions coexistent dans le système : le nom de classe de
        l'événement ("EvenementVenteCreee", émis par le domaine ventes) et sa
        forme snake_case ("vente_creee", émise par les producteurs génériques
        via ServiceSynchronisation.inscrire_dans_outbox). Les deux désignent
        le même événement métier et doivent router vers le même gestionnaire.
        """
        if type_evenement in cls.ROUTAGE:
            return type_evenement
        for nom_classe in cls.ROUTAGE:
            corps = nom_classe.removeprefix("Evenement")
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", corps).lower()
            if type_evenement == snake:
                return nom_classe
        return type_evenement

    def _router_evenement(self, entree: EntreeOutbox) -> None:
        """Délègue le traitement à la méthode spécialisée."""
        methode_nom = self.ROUTAGE.get(self._nom_canonique(entree.type_evenement))
        if methode_nom is None:
            logger.warning(
                "Outbox : type d'événement non routé '%s' (id=%s). Échec définitif.",
                entree.type_evenement, entree.id,
            )
            raise ValueError(f"Type d'événement non reconnu : {entree.type_evenement}")
        methode = getattr(self, methode_nom, None)
        if methode is None:
            logger.error(
                "Outbox : méthode '%s' introuvable sur ProcesseurOutbox.", methode_nom
            )
            raise ValueError(f"Routeur interne invalide pour : {entree.type_evenement}")
        methode(entree)

    # ─── Gestionnaires par type d'événement ──────────────────────────────────

    def _traiter_vente_creee(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="vente_creee",
            modele_source="Vente",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )
        logger.debug("Outbox : vente %s inscrite pour synchronisation.", entree.id_objet)

    def _traiter_vente_annulee(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="vente_annulee",
            modele_source="Vente",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_avoir_cree(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="avoir_cree",
            modele_source="Vente",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )
        logger.debug("Outbox : avoir %s inscrit pour synchronisation.", entree.id_objet)

    def _traiter_stock_ajuste(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="stock_ajuste",
            modele_source="Lot",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_livraison(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="livraison_receptionnee",
            modele_source="BonCommande",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_alerte_stock(self, entree: EntreeOutbox) -> None:
        from gestion.stocks.models import AlerteStock, NiveauAlerte
        donnees = entree.charge_utile
        id_medicament = donnees.get("id_medicament")
        if id_medicament:
            niveau = (
                NiveauAlerte.RUPTURE if donnees.get("est_en_rupture")
                else NiveauAlerte.ALERTE
            )
            AlerteStock.objects.get_or_create(
                medicament_id=id_medicament,
                niveau=niveau,
                est_resolue=False,
                defaults={
                    "stock_au_moment_alerte": donnees.get("stock_actuel", 0),
                    "seuil_depasse": donnees.get("seuil_alerte", 0),
                },
            )

    def _traiter_ordonnance(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="ordonnance_numerisee",
            modele_source="Ordonnance",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_connexion(self, entree: EntreeOutbox) -> None:
        donnees = entree.charge_utile
        if donnees.get("success"):
            logger.info(
                "Outbox : connexion réussie pour '%s' depuis %s",
                donnees.get("email", "?"),
                donnees.get("adresse_ip", "?"),
            )
        else:
            logger.warning(
                "Outbox : tentative de connexion échouée pour '%s' depuis %s",
                donnees.get("email_tente", "?"),
                donnees.get("adresse_ip", "?"),
            )

    def _traiter_compte_cree(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="compte_cree",
            modele_source="UtilisateurPharmacien",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_cloture_caisse(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="cloture_caisse",
            modele_source="ClotureCaisse",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    def _traiter_produit_controle(self, entree: EntreeOutbox) -> None:
        from gestion.synchronisation.modeles import EvenementSynchronisation
        EvenementSynchronisation.objects.create(
            type_evenement="produit_controle_delivre",
            modele_source="RegistreProduitsControles",
            id_objet=str(entree.id_objet),
            statut="en_attente",
            charge_utile=entree.charge_utile,
        )

    # ─── Statistiques ─────────────────────────────────────────────────────────

    @staticmethod
    def statistiques() -> dict:
        from django.db.models import Count
        stats = EntreeOutbox.objects.values("statut").annotate(total=Count("id"))
        return {row["statut"]: row["total"] for row in stats}
