"""Vues DRF du module Fournisseurs / Achats.

Contrôle d'accès :
  - Lecture (list/retrieve/réceptions) → niveau Gestionnaire de stock minimum.
  - Écriture (create, envoyer, annuler, réceptionner) → niveau Gestionnaire de stock minimum.
    La docstring originale mentionnait Gestionnaire stock / Titulaire ;
    le check a_permission_role('gestionnaire_stock') respecte la hiérarchie :
    gestionnaire_stock, pharmacien_adjoint, titulaire, administrateur sont
    tous autorisés (niveau ≥ 3).

BUG FIX (audit v2) : les trois vues utilisaient uniquement permission_classes=[IsAuthenticated],
ce qui permettait à n'importe quel utilisateur connecté — y compris un simple Caissier —
de créer/envoyer/annuler des bons de commande et réceptionner du stock.
Corrigé : permission_classes=[EstGestionnaireStockOuPlus] sur les trois vues.
"""

from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstGestionnaireStockOuPlus  # niveau ≥ 3 : gestionnaire, adjoint, titulaire, admin
from gestion.fournisseurs.models import (
    BonCommande,
    Fournisseur,
    ReceptionBonCommande,
)
from gestion.fournisseurs.serialiseurs import (
    BonCommandeSerialiseur,
    CreerBonCommandeSerialiseur,
    FournisseurSerialiseur,
    ReceptionBonCommandeSerialiseur,
    ReceptionnerBonCommandeSerialiseur,
)
from gestion.fournisseurs.services import (
    ErreurFournisseur,
    LigneBCEntree,
    LigneReceptionEntree,
    ServiceFournisseurs,
)


class VueFournisseur(viewsets.ModelViewSet):
    """CRUD Fournisseur — restreint aux rôles Gestionnaire stock / Titulaire (niveau ≥ 3)."""

    queryset = Fournisseur.objects.all().order_by("nom")
    serializer_class = FournisseurSerialiseur
    permission_classes = [EstGestionnaireStockOuPlus]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get("actif")
        recherche = self.request.query_params.get("q")
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ("1", "true", "oui"))
        if recherche:
            qs = qs.filter(nom__icontains=recherche) | qs.filter(code__icontains=recherche)
        return qs.distinct()


class VueBonCommande(viewsets.ModelViewSet):
    """
    Bons de commande : list / retrieve / create / envoyer / annuler / réceptionner.
    La création passe par un sérialiseur d'entrée dédié qui délègue au service.
    Accès restreint au niveau Gestionnaire de stock minimum (niveau ≥ 3).
    """

    queryset = BonCommande.objects.select_related("fournisseur", "cree_par").prefetch_related("lignes__medicament")
    serializer_class = BonCommandeSerialiseur
    permission_classes = [EstGestionnaireStockOuPlus]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get("statut")
        fournisseur = self.request.query_params.get("fournisseur")
        if statut:
            qs = qs.filter(statut=statut)
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        return qs.order_by("-cree_le")

    def create(self, request, *args, **kwargs):
        entree = CreerBonCommandeSerialiseur(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            bc = ServiceFournisseurs.creer_bon_commande(
                utilisateur=request.user,
                fournisseur_id=entree.validated_data["fournisseur_id"],
                lignes=[
                    LigneBCEntree(
                        medicament_id=l["medicament_id"],
                        quantite=l["quantite"],
                        prix_unitaire_ht=l["prix_unitaire_ht"],
                        taux_tva=l.get("taux_tva", Decimal("0.00")),
                        notes=l.get("notes", ""),
                    )
                    for l in entree.validated_data["lignes"]
                ],
                date_livraison_prevue=entree.validated_data.get("date_livraison_prevue"),
                notes=entree.validated_data.get("notes", ""),
            )
        except ErreurFournisseur as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Fournisseur.DoesNotExist:
            return Response({"detail": "Fournisseur introuvable ou inactif."}, status=status.HTTP_404_NOT_FOUND)
        return Response(BonCommandeSerialiseur(bc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="envoyer")
    def envoyer(self, request, pk=None):
        try:
            bc = ServiceFournisseurs.envoyer_bon_commande(
                utilisateur=request.user, bon_commande_id=pk
            )
        except ErreurFournisseur as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BonCommandeSerialiseur(bc).data)

    @action(detail=True, methods=["post"], url_path="annuler")
    def annuler(self, request, pk=None):
        motif = request.data.get("motif", "").strip()
        if not motif:
            return Response({"detail": "Motif requis."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            bc = ServiceFournisseurs.annuler_bon_commande(
                utilisateur=request.user, bon_commande_id=pk, motif=motif
            )
        except ErreurFournisseur as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BonCommandeSerialiseur(bc).data)

    @action(detail=True, methods=["post"], url_path="receptionner")
    def receptionner(self, request, pk=None):
        entree = ReceptionnerBonCommandeSerialiseur(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            reception = ServiceFournisseurs.receptionner(
                utilisateur=request.user,
                bon_commande_id=pk,
                lignes=[
                    LigneReceptionEntree(
                        ligne_bc_id=l["ligne_bc_id"],
                        quantite_recue=l["quantite_recue"],
                        numero_lot=l["numero_lot"],
                        date_peremption=l["date_peremption"],
                        prix_achat_unitaire=l["prix_achat_unitaire"],
                    )
                    for l in entree.validated_data["lignes"]
                ],
                numero_bordereau=entree.validated_data.get("numero_bordereau", ""),
                notes=entree.validated_data.get("notes", ""),
            )
        except ErreurFournisseur as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ReceptionBonCommandeSerialiseur(reception).data,
            status=status.HTTP_201_CREATED,
        )


class VueReception(viewsets.ReadOnlyModelViewSet):
    """Consultation seule des réceptions — la création passe par VueBonCommande.
    Accès restreint au niveau Gestionnaire de stock minimum (niveau ≥ 3).
    """

    queryset = ReceptionBonCommande.objects.select_related("bon_commande", "recu_par").prefetch_related("lignes")
    serializer_class = ReceptionBonCommandeSerialiseur
    permission_classes = [EstGestionnaireStockOuPlus]

    def get_queryset(self):
        qs = super().get_queryset()
        bc = self.request.query_params.get("bon_commande")
        if bc:
            qs = qs.filter(bon_commande_id=bc)
        return qs.order_by("-date_reception")
