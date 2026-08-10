"""
Extension patchée à VueVente pour ajouter l'action `recu` (impression).

Ce fichier est importé au chargement de l'app `ventes` (voir apps.py) et
attache une méthode d'action supplémentaire à VueVente sans réécrire le
fichier `vues.py` d'origine. Il produit un DTO exploitable par tout gabarit
de reçu (thermique 58 mm, thermique 80 mm, A4).

CORRECTION AUDIT v2 (P3 — traçabilité des impressions) :
  - action_recu() incrémente désormais Vente.nb_impressions à chaque appel
    via F() expression + update() atomique (pas de race condition).
  - Le champ reimprime dans le DTO reflète la vraie valeur serveur
    (nb_impressions > 1) plutôt qu'un False hardcodé.
  - Un caissier sur un second poste verra bien DUPLICATA sans que
    le premier poste ait besoin de le signaler.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.db.models import F
from django.shortcuts import get_object_or_404


def _construire_dto_recu(vente) -> Dict[str, Any]:
    """Sérialise une vente au format « reçu » conforme au §4.4.3."""
    pharmacie = _infos_pharmacie()
    lignes = []
    for ligne in vente.lignes.select_related("medicament", "lot").all():
        lignes.append({
            "medicament":            ligne.medicament.nom,
            "code":                  getattr(ligne.medicament, "code", "") or "",
            "quantite":              ligne.quantite,
            "prix_unitaire":         str(ligne.prix_unitaire),
            "taux_remise":           str(ligne.taux_remise),
            "prix_unitaire_final":   str(ligne.prix_unitaire_apres_remise),
            "montant":               str(ligne.montant_total),
            "numero_lot":            getattr(ligne.lot, "numero_lot", "") or "",
            "date_peremption":       (
                ligne.lot.date_peremption.isoformat()
                if getattr(ligne.lot, "date_peremption", None) else None
            ),
            "necessite_tracabilite": bool(
                getattr(ligne.medicament, "necessite_tracabilite_lot", False)
            ),
        })
    return {
        "pharmacie":        pharmacie,
        "numero_facture":   vente.numero,
        "date":             vente.cree_le.isoformat(),
        "caissier":         _identite_vendeur(vente.vendeur),
        "client": (
            {"id": str(vente.client.id), "nom": getattr(vente.client, "nom", "")}
            if vente.client_id else None
        ),
        "lignes":           lignes,
        "sous_total":       str(vente.sous_total),
        "montant_remise":   str(vente.montant_remise),
        "montant_total":    str(vente.montant_total),
        "montant_encaisse": str(vente.montant_encaisse),
        "montant_rendu":    str(vente.montant_rendu),
        "mode_paiement":    vente.mode_paiement,
        "statut":           vente.statut,
        "ordonnance_id":    str(vente.ordonnance_id) if vente.ordonnance_id else None,
        # reimprime est True dès la 2e impression (nb_impressions déjà incrémenté avant cet appel)
        "reimprime":        vente.nb_impressions > 1,
    }


def _infos_pharmacie() -> Dict[str, Any]:
    """
    Renvoie les infos de la pharmacie depuis les settings — permet à un
    déploiement de personnaliser sans schéma dédié pour la phase pilote.
    """
    from django.conf import settings
    return {
        "nom":             getattr(settings, "PHARMACIE_NOM", "PharmApp"),
        "adresse":         getattr(settings, "PHARMACIE_ADRESSE", ""),
        "telephone":       getattr(settings, "PHARMACIE_TELEPHONE", ""),
        "numero_agrement": getattr(settings, "PHARMACIE_AGREMENT", ""),
        "ville":           getattr(settings, "PHARMACIE_VILLE", "Bobo-Dioulasso"),
        "devise":          getattr(settings, "DEVISE", "FCFA"),
    }


def _identite_vendeur(vendeur) -> Dict[str, Any]:
    if not vendeur:
        return {"id": None, "nom": "", "matricule": ""}
    nom_complet = " ".join(
        filter(None, [getattr(vendeur, "prenom", ""), getattr(vendeur, "nom", "")])
    ) or getattr(vendeur, "username", "")
    return {
        "id":        str(getattr(vendeur, "id", "")),
        "nom":       nom_complet.strip(),
        "matricule": getattr(vendeur, "matricule", "") or "",
    }


def action_recu(self, request, pk=None):
    """
    GET /ventes/{pk}/recu/

    1. Incrémente nb_impressions atomiquement (F() expression — pas de race condition).
    2. Recharge la vente avec la nouvelle valeur.
    3. Retourne le DTO reçu avec reimprime correctement positionné.
    """
    from gestion.ventes.models import Vente

    # Incrément atomique — ne nécessite pas de select_for_update()
    # car F() génère un UPDATE SET nb_impressions = nb_impressions + 1
    # qui est atomique au niveau du moteur SQL.
    updated = Vente.objects.filter(pk=pk).update(nb_impressions=F("nb_impressions") + 1)
    if updated == 0:
        from django.http import Http404
        raise Http404

    vente = get_object_or_404(
        Vente.objects.select_related("vendeur", "client")
                     .prefetch_related("lignes__medicament", "lignes__lot"),
        pk=pk,
    )
    return Response(_construire_dto_recu(vente), status=status.HTTP_200_OK)


def brancher_action_recu(vue_vente_cls):
    """Attache dynamiquement l'action `recu` à VueVente."""
    if getattr(vue_vente_cls, "recu", None):
        return
    decore = action(detail=True, methods=["get"], url_path="recu")(action_recu)
    vue_vente_cls.recu = decore
