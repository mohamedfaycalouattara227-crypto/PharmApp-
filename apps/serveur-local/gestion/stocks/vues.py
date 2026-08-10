"""
gestion/stocks/vues.py
Vues DRF pour les stocks : mouvements, alertes, inventaires.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstGestionnaireStock, EstPharmacienAdjoint
from gestion.stocks.services import ServiceStock


class VueStock(viewsets.ViewSet):
    """Gestion des stocks : ajustements, besoins de réapprovisionnement."""

    permission_classes = [EstGestionnaireStock]

    def list(self, request):
        """Liste des inventaires."""
        from gestion.stocks.models import Inventaire
        from gestion.stocks.serialiseurs import InventaireSerialiseur
        inventaires = Inventaire.objects.all().order_by("-cree_le")
        return Response(InventaireSerialiseur(inventaires, many=True).data)

    @action(detail=False, methods=["post"])
    def ajuster(self, request):
        """Ajuste manuellement le stock d'un lot."""
        from gestion.exceptions import (
            PermissionRefusee, LotInactif, EcartInventaireSignificatif,
        )

        # ── Validation des champs obligatoires avant tout accès DB ────────────
        lot_id = request.data.get("lot_id")
        if not lot_id:
            return Response(
                {"erreur": "Le champ 'lot_id' est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nouvelle_quantite_raw = request.data.get("nouvelle_quantite")
        if nouvelle_quantite_raw is None:
            return Response(
                {"erreur": "Le champ 'nouvelle_quantite' est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            nouvelle_quantite = int(nouvelle_quantite_raw)
        except (TypeError, ValueError):
            return Response(
                {"erreur": "'nouvelle_quantite' doit être un entier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Appel service ──────────────────────────────────────────────────────
        try:
            lot = ServiceStock().ajuster_stock_manuel(
                lot_id=lot_id,
                nouvelle_quantite=nouvelle_quantite,
                motif=request.data.get("motif", ""),
                utilisateur=request.user,
                adresse_ip=request.META.get("REMOTE_ADDR", ""),
            )
            return Response({"message": "Stock ajusté.", "lot_id": str(lot.id)})
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LotInactif as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except EcartInventaireSignificatif as exc:
            return Response(
                {"erreur": str(exc), "code": "ecart_significatif"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="besoins-reappro")
    def besoins_reappro(self, request):
        """Retourne les médicaments sous le seuil d'alerte via le service."""
        besoins = ServiceStock().calculer_besoins_reapprovisionnement()
        return Response(besoins)

    @action(detail=False, methods=["post"])
    def demarrer_inventaire(self, request):
        """Démarre un nouvel inventaire."""
        from gestion.stocks.models import Inventaire
        from gestion.stocks.serialiseurs import InventaireSerialiseur
        from django.utils import timezone

        if not request.user.a_permission_role("gestionnaire_stock"):
            return Response(
                {"erreur": "Permission insuffisante."},
                status=status.HTTP_403_FORBIDDEN,
            )

        inventaire = Inventaire.objects.create(
            reference=request.data.get("reference", f"INV-{timezone.now().strftime('%Y%m%d-%H%M%S')}"),
            demarre_par=request.user,
        )
        return Response(
            InventaireSerialiseur(inventaire).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Mouvements de stock (Étape 2) ──────────────────────────────────────
    @action(detail=False, methods=["get"])
    def mouvements(self, request):
        """
        Liste paginée des mouvements de stock.

        Filtres query-string acceptés :
          lot_id          — UUID du lot concerné
          medicament_id   — UUID du médicament (filtre sur lot__medicament)
          type_mouvement  — ex. "vente", "reception", "ajustement_plus"…
          date_debut      — ISO 8601 (inclus)
          date_fin        — ISO 8601 (inclus)
        """
        from gestion.stocks.models import MouvementStock
        from gestion.stocks.serialiseurs import MouvementStockSerialiseur
        from rest_framework.pagination import PageNumberPagination

        qs = (
            MouvementStock.objects
            .select_related("lot__medicament", "effectue_par")
            .all()
        )

        lot_id = request.query_params.get("lot_id")
        if lot_id:
            qs = qs.filter(lot_id=lot_id)

        medicament_id = request.query_params.get("medicament_id")
        if medicament_id:
            qs = qs.filter(lot__medicament_id=medicament_id)

        type_mouvement = request.query_params.get("type_mouvement")
        if type_mouvement:
            qs = qs.filter(type_mouvement=type_mouvement)

        date_debut = request.query_params.get("date_debut")
        if date_debut:
            qs = qs.filter(cree_le__date__gte=date_debut)

        date_fin = request.query_params.get("date_fin")
        if date_fin:
            qs = qs.filter(cree_le__date__lte=date_fin)

        paginator = PageNumberPagination()
        # DT-022 (corrigé) : borner page_size pour éviter un DoS par requête lourde.
        # Maximum 200 entrées par page ; par défaut 50.
        paginator.page_size = min(
            int(request.query_params.get("page_size", 50)),
            200,
        )
        page = paginator.paginate_queryset(qs, request)
        serisl = MouvementStockSerialiseur(page, many=True)
        return paginator.get_paginated_response(serisl.data)


class VueAlerteStock(viewsets.ModelViewSet):
    """Gestion des alertes de stock, réservée au gestionnaire minimum."""
    permission_classes = [EstGestionnaireStock]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        from gestion.stocks.models import AlerteStock
        # Recalculer les alertes à la lecture garantit que l’API reflète le stock
        # courant, même lorsqu’aucun job périodique n’a encore tourné.
        ServiceStock().verifier_alertes_stock()
        qs = AlerteStock.objects.select_related("medicament").order_by("-cree_le")
        est_resolue = self.request.query_params.get("est_resolue")
        if est_resolue is not None:
            qs = qs.filter(est_resolue=est_resolue.lower() == "true")
        return qs

    def get_serializer_class(self):
        from gestion.stocks.serialiseurs import AlerteStockSerialiseur
        return AlerteStockSerialiseur

    def partial_update(self, request, pk=None):
        """Marque une alerte comme résolue."""
        from gestion.stocks.models import AlerteStock
        from django.utils import timezone

        try:
            alerte = AlerteStock.objects.get(pk=pk)
        except AlerteStock.DoesNotExist:
            return Response({"erreur": "Alerte introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if request.data.get("est_resolue"):
            alerte.est_resolue = True
            alerte.resolue_le = timezone.now()
            alerte.save()

        from gestion.stocks.serialiseurs import AlerteStockSerialiseur
        return Response(AlerteStockSerialiseur(alerte).data)
