"""
gestion/ordonnances/vues.py
Vues DRF pour les ordonnances.

ÉTAPE 10 — Upload multipart d'image d'ordonnance (§4.5 CDC) :
  POST /api/ordonnances/  — multipart avec champ 'fichier'
  Le fichier est chiffré AES-256-GCM avant stockage.
  Aucune image n'est stockée en clair sur disque.

Flux (§4.5 CDC) :
  1. Caissier/pharmacien upload l'image → ordonnance créée avec statut EN_ATTENTE
  2. Pharmacien valide l'ordonnance → statut VALIDEE
  3. L'ordonnance_id est inclus dans le payload de création de vente
"""

import logging
import uuid
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action

logger = logging.getLogger("pharmapp.ordonnances")
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstCaissier, EstPharmacienAdjoint
from gestion.ordonnances.models import Ordonnance
from gestion.ordonnances.services import ServiceOrdonnance
from django.http import HttpResponse


class VueOrdonnance(viewsets.ModelViewSet):
    """CRUD des ordonnances avec upload sécurisé d'images."""

    permission_classes = [EstCaissier]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Ordonnance.objects.select_related("client", "numerisee_par", "validee_par").all()
        statut = self.request.query_params.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        client_id = self.request.query_params.get("client")
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs.order_by("-cree_le")

    def get_serializer_class(self):
        from gestion.ordonnances.serialiseurs import OrdonnanceSerialiseur
        return OrdonnanceSerialiseur

    def create(self, request, *args, **kwargs):
        """
        Upload d'une ordonnance (multipart) ou création sans image.
        Si un fichier est fourni, il est chiffré AES-256-GCM avant stockage.
        """
        from gestion.ordonnances.models import Ordonnance, StatutOrdonnance
        from gestion.ordonnances.serialiseurs import OrdonnanceSerialiseur

        fichier = request.FILES.get("fichier")
        client_id = request.data.get("client_id") or request.data.get("client")
        prescripteur_nom = (request.data.get("prescripteur_nom") or "Non renseigné").strip()
        prescripteur_etablissement = (request.data.get("prescripteur_etablissement") or "").strip()
        date_prescription_str = request.data.get("date_prescription")
        notes = (request.data.get("notes") or "").strip()

        # Date de prescription
        from datetime import date
        date_prescription = None
        if date_prescription_str:
            try:
                date_prescription = date.fromisoformat(date_prescription_str)
            except ValueError:
                date_prescription = date.today()
        else:
            date_prescription = date.today()

        # Générer le numéro interne
        numero_interne = f"ORD-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Résoudre le client (optionnel)
        client = None
        if client_id:
            try:
                from gestion.clients.models import Client
                client = Client.objects.get(pk=client_id)
            except Client.DoesNotExist:
                return Response(
                    {"client_id": [f"Client introuvable (ID={client_id})."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as exc:
                logger.warning("Résolution client pk=%s pour ordonnance échouée : %s", client_id, exc)
                return Response(
                    {"client_id": ["Erreur lors de la résolution du client."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Créer l'ordonnance
        ordonnance = Ordonnance(
            numero_interne=numero_interne,
            client=client,
            prescripteur_nom=prescripteur_nom,
            prescripteur_etablissement=prescripteur_etablissement,
            date_prescription=date_prescription,
            statut=StatutOrdonnance.EN_ATTENTE,
            numerisee_par=request.user,
            notes=notes,
        )

        # Chiffrer et stocker l'image si fournie
        if fichier:
            contenu = fichier.read()
            type_mime_declare = fichier.content_type or ""
            from gestion.ordonnances.services import (
                ServiceChiffrementOrdonnance,
                valider_image_ordonnance,
            )
            # NE PAS faire confiance à fichier.content_type : sniff des magic
            # bytes + refus si le type déclaré diverge du contenu réel.
            type_mime_reel = valider_image_ordonnance(contenu, type_mime_declare)
            service = ServiceChiffrementOrdonnance()
            nonce, chiffre = service.chiffrer(contenu, associe=None)
            ordonnance.image_chiffree = chiffre
            ordonnance.vecteur_initialisation = nonce
            ordonnance.type_mime = type_mime_reel
            ordonnance.taille_image_octets = len(contenu)

        ordonnance.save()

        return Response(
            OrdonnanceSerialiseur(ordonnance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="image", permission_classes=[EstPharmacienAdjoint])
    def image(self, request, pk=None):
        """Déchiffre et retourne l'image d'une ordonnance."""
        try:
            ordonnance = Ordonnance.objects.get(pk=pk)
        except Ordonnance.DoesNotExist:
            return Response({"erreur": "Ordonnance introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not ordonnance.image_chiffree:
            return Response({"erreur": "Aucune image associée."}, status=status.HTTP_404_NOT_FOUND)

        try:
            service = ServiceOrdonnance()
            contenu = service.consulter_image(ordonnance)
            return HttpResponse(contenu, content_type=ordonnance.type_mime)
        except Exception as exc:
            logger.error("Erreur consultation image ordonnance pk=%s : %s", pk, exc)
            return Response({"erreur": "Erreur lors du déchiffrement de l'image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="valider", permission_classes=[EstPharmacienAdjoint])
    def valider(self, request, pk=None):
        """Valide une ordonnance — réservé pharmacien adjoint+."""
        from gestion.ordonnances.models import Ordonnance, StatutOrdonnance
        from gestion.ordonnances.serialiseurs import OrdonnanceSerialiseur
        try:
            ordonnance = Ordonnance.objects.get(pk=pk)
        except Ordonnance.DoesNotExist:
            return Response({"erreur": "Ordonnance introuvable."}, status=status.HTTP_404_NOT_FOUND)
        ordonnance.statut = StatutOrdonnance.VALIDEE
        ordonnance.validee_par = request.user
        ordonnance.validee_le = timezone.now()
        ordonnance.save()
        return Response(OrdonnanceSerialiseur(ordonnance).data)
