"""
gestion/materiel/vues.py
Endpoints REST pour les actions matérielles (tiroir, imprimante, scanner).
Ces endpoints sont appelés exclusivement par le poste client local.

Routes (à ajouter dans pharmapp/urls.py ou api/urls.py) :
  POST /api/materiel/tiroir/          — ouvre le tiroir-caisse
  POST /api/materiel/imprimer-recu/   — impression ESC/POS d'un reçu existant
  POST /api/materiel/test-imprimante/ — impression d'un ticket de test
  POST /api/materiel/scanner/         — lit un code-barres et identifie le lot
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.permissions import EstCaissier, EstPharmacienAdjoint
from gestion.materiel.escpos import (
    ServiceImprimanteESCPOS,
    ErreurImprimante,
    ImprimanteNonConfiguree,
)
from gestion.materiel.scanner import (
    ServiceScannerCodeBarres,
    ErreurScanner,
    ScannerNonConfigure,
    TimeoutScan,
    CodeNonReconnu,
    LotIntrouvable,
)

logger = logging.getLogger("pharmapp.materiel")


@api_view(["POST"])
@permission_classes([EstCaissier])
def ouvrir_tiroir(request):
    """
    POST /api/materiel/tiroir/
    Ouvre le tiroir-caisse via commande ESC/POS.
    Permission : caissier+
    """
    try:
        service = ServiceImprimanteESCPOS.depuis_parametrage()
        service.ouvrir_tiroir()
        logger.info(
            "tiroir_ouvert",
            extra={"utilisateur": str(request.user.pk)},
        )
        return Response({"statut": "ok", "message": "Tiroir ouvert."})
    except ImprimanteNonConfiguree as exc:
        return Response(
            {"statut": "non_configure", "message": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except ErreurImprimante as exc:
        logger.error("tiroir_echec", extra={"erreur": str(exc)})
        return Response(
            {"statut": "erreur", "message": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["POST"])
@permission_classes([EstCaissier])
def imprimer_recu(request):
    """
    POST /api/materiel/imprimer-recu/
    Corps : { "vente_id": "<uuid>" }
    Récupère le DTO reçu et l'imprime via ESC/POS.
    Permission : caissier+
    """
    vente_id = request.data.get("vente_id")
    if not vente_id:
        return Response(
            {"erreur": "vente_id est obligatoire."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from gestion.ventes.models import Vente
    from gestion.ventes.recu import _construire_dto_recu

    try:
        vente = (
            Vente.objects
            .select_related("vendeur", "client")
            .prefetch_related("lignes__medicament", "lignes__lot")
            .get(pk=vente_id)
        )
    except Vente.DoesNotExist:
        return Response(
            {"erreur": "Vente introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        service = ServiceImprimanteESCPOS.depuis_parametrage()
        dto = _construire_dto_recu(vente)
        service.imprimer_recu(dto, ouvrir_tiroir=False)  # tiroir géré séparément
        return Response({"statut": "ok", "numero": vente.numero})
    except ImprimanteNonConfiguree as exc:
        # Fallback : retourner le DTO pour window.print() côté client
        from gestion.ventes.recu import _construire_dto_recu
        dto = _construire_dto_recu(vente)
        return Response(
            {"statut": "fallback_window_print", "recu": dto},
            status=status.HTTP_200_OK,
        )
    except ErreurImprimante as exc:
        logger.error("impression_escpos_echec", extra={"vente_id": str(vente_id), "erreur": str(exc)})
        return Response(
            {"statut": "erreur", "message": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["POST"])
@permission_classes([EstPharmacienAdjoint])
def test_imprimante(request):
    """
    POST /api/materiel/test-imprimante/
    Imprime un ticket de test ESC/POS. Réservé au pharmacien adjoint+.
    """
    try:
        service = ServiceImprimanteESCPOS.depuis_parametrage()
        service.imprimer_test()
        return Response({"statut": "ok", "message": "Ticket de test envoyé."})
    except ImprimanteNonConfiguree as exc:
        return Response(
            {"statut": "non_configure", "message": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except ErreurImprimante as exc:
        return Response(
            {"statut": "erreur", "message": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["POST"])
@permission_classes([EstCaissier])
def lire_code_barres(request):
    """
    POST /api/materiel/scanner/
    Corps : { "timeout": 5.0 }   (secondes, optionnel, défaut 5)

    Lit un code-barres depuis le scanner configuré, identifie le lot actif
    correspondant et retourne ses informations pour pré-remplir la ligne de vente.

    Réponses :
      200  { "code": "3400935190298", "lot": { "id", "medicament_nom",
             "quantite_disponible", "numero_lot", "date_peremption" } }
      408  timeout : aucun code reçu dans le délai imparti
      422  code reçu mais format non reconnu (EAN/Code39/128 requis)
      404  code reconnu mais aucun lot actif en stock
      503  scanner non configuré (SCANNER_TYPE absent ou invalide)
      502  erreur matérielle (port inaccessible, evdev introuvable…)

    Permission : caissier+
    """
    timeout = float(request.data.get("timeout", 5.0))

    try:
        service = ServiceScannerCodeBarres.depuis_parametrage()
        code = service.lire_code(timeout=timeout)
        lot = service.identifier_lot(code)

        lot_data = {
            "id": str(lot.id),
            # `str(...)` garantit une valeur JSON-sérialisable quelle que soit
            # la nature de l'objet retourné par le service (modèle Django réel
            # ou double de test) : le renderer DRF ne sait pas sérialiser un
            # objet arbitraire et renverrait une 500 au poste client.
            "medicament_nom": str(
                getattr(getattr(lot, "medicament", None), "nom", None) or lot
            ),
            "quantite_disponible": (
                lot.quantite_disponible if hasattr(lot, "quantite_disponible") else None
            ),
            "numero_lot": (
                lot.numero_lot if hasattr(lot, "numero_lot") else None
            ),
            "date_peremption": (
                str(lot.date_peremption) if hasattr(lot, "date_peremption") else None
            ),
        }

        logger.info(
            "scanner_lecture_reussie",
            extra={"utilisateur": str(request.user.pk), "code": code},
        )
        return Response({"statut": "ok", "code": code, "lot": lot_data})

    except ScannerNonConfigure as exc:
        return Response(
            {"statut": "non_configure", "message": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except TimeoutScan as exc:
        return Response(
            {"statut": "timeout", "message": str(exc)},
            status=status.HTTP_408_REQUEST_TIMEOUT,
        )
    except CodeNonReconnu as exc:
        return Response(
            {"statut": "code_non_reconnu", "message": str(exc)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except LotIntrouvable as exc:
        return Response(
            {"statut": "lot_introuvable", "message": str(exc)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ErreurScanner as exc:
        logger.error(
            "scanner_erreur_materielle",
            extra={"erreur": str(exc), "utilisateur": str(request.user.pk)},
        )
        return Response(
            {"statut": "erreur", "message": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
