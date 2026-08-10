"""
gestion/parametrage/vues.py
Endpoint REST pour le singleton Paramétrage.

GET  /api/parametrage/  → lecture (tout utilisateur authentifié)
PATCH /api/parametrage/ → modification (titulaire uniquement)
"""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import EstAuthentifie, EstTitulaire
from gestion.parametrage.models import Parametrage
from gestion.parametrage.serialiseurs import ParametrageSerialiseur


class VueParametrage(APIView):
    """
    Singleton paramétrage pharmacie.

    GET  → accessible à tout utilisateur authentifié (reçu, impression…).
    PATCH → réservé au titulaire (EstTitulaire).
    """

    def get_permissions(self):  # type: ignore[override]
        if self.request.method in ("PATCH", "PUT"):
            return [EstTitulaire()]
        return [EstAuthentifie()]

    def get(self, request: Request) -> Response:
        """Retourne le paramétrage courant (crée le singleton si absent)."""
        parametrage = Parametrage.obtenir()
        serisl = ParametrageSerialiseur(parametrage, context={"request": request})
        return Response(serisl.data)

    def patch(self, request: Request) -> Response:
        """Mise à jour partielle du paramétrage."""
        parametrage = Parametrage.obtenir()
        serisl = ParametrageSerialiseur(
            parametrage,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serisl.is_valid():
            serisl.save()
            return Response(serisl.data)
        return Response(serisl.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request: Request) -> Response:
        """Remplacement complet — délégué au PATCH pour simplifier."""
        return self.patch(request)
