"""
gestion/clients/vues.py
Vues DRF pour les clients.

ÉTAPE 5 — Correction get_serializer_context() pour passer le request au serializer.
Sans ce passage, le sérialiseur ne peut pas appliquer la restriction allergies par rôle.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstCaissier, EstPharmacienAdjoint, EstTitulaire
from gestion.clients.services import ServiceClient


class VueClient(viewsets.ModelViewSet):
    """CRUD des clients de la pharmacie."""

    permission_classes = [EstCaissier]

    def get_serializer_context(self):
        """Passe le request au sérialiseur pour la restriction allergies par rôle (§7.2)."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        from gestion.clients.models import Client
        qs = Client.objects.all()
        est_actif = self.request.query_params.get("est_actif")
        if est_actif is not None:
            qs = qs.filter(est_actif=est_actif.lower() == "true")
        search = self.request.query_params.get("search") or self.request.query_params.get("q")
        if search:
            qs = (
                qs.filter(nom__icontains=search)
                | qs.filter(prenom__icontains=search)
                | qs.filter(telephone__icontains=search)
            )
        return qs.order_by("nom", "prenom")

    def get_serializer_class(self):
        from gestion.clients.serialiseurs import ClientSerialiseur
        return ClientSerialiseur

    def create(self, request, *args, **kwargs):
        from gestion.exceptions import PermissionRefusee, TelephoneDejaUtilise
        from gestion.clients.serialiseurs import ClientSerialiseur

        service = ServiceClient()
        try:
            client = service.creer_client(
                prenom=request.data.get("prenom", ""),
                nom=request.data.get("nom", ""),
                donnees=request.data,
                utilisateur=request.user,
            )
            return Response(
                ClientSerialiseur(client, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except TelephoneDejaUtilise as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        from gestion.exceptions import PermissionRefusee
        from gestion.clients.serialiseurs import ClientSerialiseur

        service = ServiceClient()
        try:
            client = service.modifier_client(
                client_id=kwargs["pk"],
                donnees=request.data,
                utilisateur=request.user,
            )
            return Response(ClientSerialiseur(client, context={"request": request}).data)
        except PermissionRefusee as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"erreur": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, *args, **kwargs):
        """Configurer le crédit nécessite pharmacien adjoint+."""
        if "credit_autorise" in request.data or "plafond_credit" in request.data:
            if not EstPharmacienAdjoint().has_permission(request, self):
                return Response(
                    {"erreur": "Configuration du crédit réservée au pharmacien adjoint+."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        # Modification allergies réservée au pharmacien adjoint+
        if "allergies" in request.data:
            if not EstPharmacienAdjoint().has_permission(request, self):
                return Response(
                    {"erreur": "Modification des allergies réservée au pharmacien adjoint+."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], permission_classes=[EstTitulaire])
    def anonymiser(self, request, pk=None):
        """Droit à l'oubli — anonymise les données du client (RGPD)."""
        try:
            from gestion.clients.models import Client
            client = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return Response({"erreur": "Client introuvable."}, status=status.HTTP_404_NOT_FOUND)
        client.anonymiser()
        from gestion.clients.serialiseurs import ClientSerialiseur
        return Response(ClientSerialiseur(client, context={"request": request}).data)
