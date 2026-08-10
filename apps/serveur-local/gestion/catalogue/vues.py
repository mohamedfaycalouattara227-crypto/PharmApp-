"""
gestion/catalogue/vues.py
Vues DRF pour le catalogue : médicaments, catégories, lots.

AJOUT étape 4 :
  - Recherche DCI (denomination_commune_internationale) en plus du nom
  - Action import_csv : upload fichier CSV CAMEG → création de médicaments en lot
"""

import csv
import io

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstGestionnaireStock, EstTitulaire


class VueMedicament(viewsets.ModelViewSet):
    """CRUD des médicaments."""

    permission_classes = [EstAuthentifie]

    def get_permissions(self):
        """Lecture : tout utilisateur authentifié. Écriture : gestionnaire de stock+."""
        if self.action in ("list", "retrieve"):
            return [EstAuthentifie()]
        return [EstGestionnaireStock()]

    def get_queryset(self):
        from gestion.catalogue.models import Medicament
        qs = Medicament.objects.select_related("categorie").all()

        est_actif = self.request.query_params.get("est_actif")
        if est_actif is not None:
            qs = qs.filter(est_actif=est_actif.lower() == "true")

        # Recherche live sur nom + DCI (§4.2 CDC — SearchFilter debounced 300ms côté frontend)
        search = self.request.query_params.get("search") or self.request.query_params.get("q")
        if search:
            qs = (
                qs.filter(nom__icontains=search)
                | qs.filter(denomination_commune_internationale__icontains=search)
                | qs.filter(code_cis__icontains=search)
                | qs.filter(code_barre__icontains=search)
            )

        categorie = self.request.query_params.get("categorie")
        if categorie:
            qs = qs.filter(categorie_id=categorie)

        prix_reglemente = self.request.query_params.get("prix_reglemente")
        if prix_reglemente is not None:
            qs = qs.filter(prix_reglemente=prix_reglemente.lower() == "true")

        return qs.distinct().order_by("nom")

    def get_serializer_class(self):
        from gestion.catalogue.serialiseurs import MedicamentSerialiseur
        return MedicamentSerialiseur

    @action(
        detail=False,
        methods=["post"],
        url_path="import-csv",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[EstGestionnaireStock],
    )
    def import_csv(self, request):
        """
        Import du référentiel CAMEG via fichier CSV.
        Format attendu (colonnes minimum) :
          nom, dci, forme, dosage, categorie, prix_public
        Retourne le nombre de médicaments créés / mis à jour.
        """
        fichier = request.FILES.get("fichier")
        if not fichier:
            return Response(
                {"detail": "Aucun fichier fourni. Champ attendu : 'fichier'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            texte = fichier.read().decode("utf-8-sig")  # gère le BOM UTF-8
        except UnicodeDecodeError:
            try:
                fichier.seek(0)
                texte = fichier.read().decode("latin-1")
            except Exception as e:
                return Response(
                    {"detail": f"Impossible de décoder le fichier : {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        reader = csv.DictReader(io.StringIO(texte))

        from gestion.catalogue.models import Medicament, CategorieProduit
        from decimal import Decimal, InvalidOperation

        crees = 0
        mis_a_jour = 0
        erreurs = []

        for i, ligne in enumerate(reader, start=2):  # ligne 1 = en-tête
            nom = (ligne.get("nom") or "").strip()
            if not nom:
                erreurs.append(f"Ligne {i} : colonne 'nom' vide — ignorée.")
                continue

            # Prix public
            prix_str = (ligne.get("prix_public") or ligne.get("prix") or "0").strip()
            try:
                prix = Decimal(prix_str.replace(",", ".").replace(" ", ""))
            except InvalidOperation:
                prix = Decimal("0.00")

            # Catégorie — crée si absente
            categorie_nom = (ligne.get("categorie") or "").strip()
            categorie = None
            if categorie_nom:
                categorie, _ = CategorieProduit.objects.get_or_create(
                    nom=categorie_nom,
                    defaults={"code": categorie_nom[:20].upper()},
                )

            defaults = {
                "denomination_commune_internationale": (ligne.get("dci") or "").strip(),
                "forme_pharmaceutique": (ligne.get("forme") or "").strip(),
                "dosage": (ligne.get("dosage") or "").strip(),
                "prix_public": prix,
                "est_actif": True,
            }
            if categorie:
                defaults["categorie"] = categorie

            code_cis = (ligne.get("code_cis") or "").strip()
            if code_cis:
                obj, created = Medicament.objects.update_or_create(
                    code_cis=code_cis,
                    defaults={"nom": nom, **defaults},
                )
            else:
                obj, created = Medicament.objects.update_or_create(
                    nom=nom,
                    defaults=defaults,
                )

            if created:
                crees += 1
            else:
                mis_a_jour += 1

        return Response({
            "crees": crees,
            "mis_a_jour": mis_a_jour,
            "erreurs": erreurs[:20],  # max 20 erreurs retournées
            "message": f"{crees} créés, {mis_a_jour} mis à jour.",
        }, status=status.HTTP_200_OK)


class VueCategorieProduit(viewsets.ModelViewSet):
    """CRUD des catégories de produits."""

    permission_classes = [EstAuthentifie]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [EstAuthentifie()]
        return [EstGestionnaireStock()]

    def get_queryset(self):
        from gestion.catalogue.models import CategorieProduit
        qs = CategorieProduit.objects.all()
        est_active = self.request.query_params.get("est_active")
        if est_active is not None:
            qs = qs.filter(est_active=est_active.lower() == "true")
        return qs.order_by("nom")

    def get_serializer_class(self):
        from gestion.catalogue.serialiseurs import CategorieProduitSerialiseur
        return CategorieProduitSerialiseur

    def destroy(self, request, *args, **kwargs):
        """Interdit la suppression d'une catégorie qui contient des médicaments actifs."""
        instance = self.get_object()
        if instance.medicaments.filter(est_actif=True).exists():
            return Response(
                {
                    "erreur": "conflit",
                    "message": "Impossible de supprimer une catégorie contenant des médicaments actifs.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VueLot(viewsets.ModelViewSet):
    """CRUD des lots de stock."""

    permission_classes = [EstGestionnaireStock]

    def get_queryset(self):
        from gestion.catalogue.models import Lot
        qs = Lot.objects.select_related("medicament").all()
        est_actif = self.request.query_params.get("est_actif")
        if est_actif is not None:
            qs = qs.filter(est_actif=est_actif.lower() == "true")
        medicament_id = self.request.query_params.get("medicament_id")
        if medicament_id:
            qs = qs.filter(medicament_id=medicament_id)
        # Filtre péremption proche — utilisé par le tableau de bord (Étape 1)
        peremption_proche = self.request.query_params.get("peremption_proche")
        if peremption_proche and peremption_proche.lower() == "true":
            from datetime import date, timedelta
            try:
                from gestion.parametrage.models import Parametrage
                seuil = Parametrage.obtenir().seuil_peremption_jours
            except Exception as exc:
                logger.warning("Impossible de lire le seuil péremption depuis Parametrage : %s", exc)
                seuil = 60
            date_limite = date.today() + timedelta(days=seuil)
            qs = qs.filter(
                est_actif=True,
                quantite_disponible__gt=0,
                date_peremption__lte=date_limite,
            )
        return qs.order_by("date_peremption")

    def get_serializer_class(self):
        from gestion.catalogue.serialiseurs import LotSerialiseur
        return LotSerialiseur
