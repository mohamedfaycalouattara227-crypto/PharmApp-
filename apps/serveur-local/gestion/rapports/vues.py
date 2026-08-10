"""
gestion/rapports/vues.py
Vues DRF pour les rapports périodiques, agrégats et exports.

ÉTAPE 8 — Nouveaux endpoints d'agrégation (§4.9 CDC) :
  GET /api/rapports/tableau-bord/       — KPIs temps réel (étape 1, déjà présent)
  GET /api/rapports/ventes/             — CA par période/caissier/produit
  GET /api/rapports/top-produits/       — top produits sur une période
  GET /api/rapports/marges/             — marges par produit (EstTitulaire uniquement)
  GET /api/rapports/ecarts-inventaire/  — écarts d'inventaire
  GET /api/rapports/export-ventes/      — export CSV ventes

Logique métier :
  - Tous les endpoints sont en LECTURE SEULE — aucun rapport ne déclenche d'écriture.
  - Les aggrégations utilisent select_related + index sur date_vente.
  - /marges/ est protégé par EstTitulaire (level 5+).
"""

import csv
import io
import logging
from datetime import timedelta, date

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstAuthentifie, EstPharmacienAdjoint, EstTitulaire

logger = logging.getLogger("pharmapp.rapports")


class VueRapport(viewsets.ReadOnlyModelViewSet):
    """Lecture des rapports pré-calculés + agrégats tableau de bord."""

    permission_classes = [EstPharmacienAdjoint]

    def get_queryset(self):
        try:
            from gestion.rapports.models import RapportGenere
            qs = RapportGenere.objects.all().order_by("-cree_le")
            type_rapport = self.request.query_params.get("type")
            if type_rapport:
                qs = qs.filter(type_rapport=type_rapport)
            return qs
        except Exception as exc:
            logger.warning("Impossible de charger RapportGenere (migration ?) : %s", exc)
            return []

    def get_serializer_class(self):
        try:
            from gestion.rapports.serialiseurs import RapportGenereSerialiseur
            return RapportGenereSerialiseur
        except Exception as exc:
            logger.warning("Impossible de charger RapportGenereSerialiseur : %s", exc)
            from rest_framework import serializers
            return serializers.Serializer

    # ── Tableau de bord (Étape 1) ──────────────────────────────────────────
    @action(
        detail=False,
        methods=["get"],
        url_path="tableau-bord",
        permission_classes=[EstAuthentifie],
    )
    def tableau_bord(self, request):
        """
        Agrégats temps réel pour le tableau de bord (§4.1 CDC).
        Permission : tout utilisateur authentifié (caissier, assistant…).
        """
        from django.db.models import Sum

        try:
            from gestion.ventes.models import Vente
        except ImportError:
            Vente = None

        try:
            from gestion.stocks.models import AlerteStock
        except ImportError:
            AlerteStock = None

        try:
            from gestion.catalogue.models import Lot
        except ImportError:
            Lot = None

        try:
            from gestion.parametrage.models import Parametrage
            seuil_jours = Parametrage.obtenir().seuil_peremption_jours
        except Exception as exc:
            logger.warning("Impossible de lire seuil_peremption_jours : %s", exc)
            seuil_jours = 60

        today = timezone.localdate()

        ca_aujourd_hui = 0
        nb_ventes_aujourd_hui = 0
        if Vente is not None:
            try:
                ventes_jour = Vente.objects.filter(cree_le__date=today, statut="validee")
                ca_agg = ventes_jour.aggregate(total=Sum("montant_total"))
                ca_aujourd_hui = ca_agg["total"] or 0
                nb_ventes_aujourd_hui = ventes_jour.count()
            except Exception as exc:
                logger.warning("Erreur calcul CA journalier : %s", exc)

        nb_alertes_stock = 0
        nb_ruptures = 0
        if AlerteStock is not None:
            try:
                nb_alertes_stock = AlerteStock.objects.filter(est_resolue=False, niveau="alerte").count()
                nb_ruptures = AlerteStock.objects.filter(est_resolue=False, niveau="rupture").count()
            except Exception as exc:
                logger.warning("Erreur comptage alertes stock : %s", exc)

        nb_peremptions_proches = 0
        if Lot is not None:
            try:
                date_limite = today + timedelta(days=seuil_jours)
                nb_peremptions_proches = Lot.objects.filter(
                    est_actif=True,
                    quantite_disponible__gt=0,
                    date_peremption__lte=date_limite,
                    date_peremption__gte=today,
                ).count()
            except Exception as exc:
                logger.warning("Erreur comptage péremptions proches : %s", exc)

        return Response({
            "ca_aujourd_hui":           str(ca_aujourd_hui),
            "nb_ventes_aujourd_hui":    nb_ventes_aujourd_hui,
            "nb_alertes_stock":         nb_alertes_stock,
            "nb_ruptures":              nb_ruptures,
            "nb_peremptions_proches":   nb_peremptions_proches,
            "seuil_peremption_jours":   seuil_jours,
        })

    # ── Étape 8 : rapport ventes par période ──────────────────────────────
    @action(detail=False, methods=["get"], url_path="ventes", permission_classes=[EstPharmacienAdjoint])
    def rapport_ventes(self, request):
        """
        CA agrégé par période, filtrable par caissier et médicament.
        GET /api/rapports/ventes/?debut=YYYY-MM-DD&fin=YYYY-MM-DD&caissier=uuid&produit=uuid
        """
        from django.db.models import Sum, Count, Avg
        try:
            from gestion.ventes.models import Vente, LigneVente
        except ImportError:
            return Response({"detail": "Module ventes indisponible."}, status=500)

        debut_str = request.query_params.get("debut")
        fin_str = request.query_params.get("fin")
        caissier_id = request.query_params.get("caissier")
        produit_id = request.query_params.get("produit")

        today = timezone.localdate()
        try:
            debut = date.fromisoformat(debut_str) if debut_str else today - timedelta(days=30)
            fin   = date.fromisoformat(fin_str)   if fin_str   else today
        except ValueError:
            return Response({"detail": "Format de date invalide (attendu YYYY-MM-DD)."}, status=400)

        qs = Vente.objects.filter(
            cree_le__date__gte=debut,
            cree_le__date__lte=fin,
            statut="validee",
        )
        if caissier_id:
            qs = qs.filter(vendeur_id=caissier_id)

        # Si filtre produit → passer par les lignes
        if produit_id:
            ids_ventes = LigneVente.objects.filter(medicament_id=produit_id).values_list("vente_id", flat=True)
            qs = qs.filter(id__in=ids_ventes)

        agg = qs.aggregate(
            ca_total=Sum("montant_total"),
            nb_ventes=Count("id"),
            remises_total=Sum("montant_remise"),
        )

        # Répartition par mode de paiement
        from django.db.models import Sum as S
        repartition = {}
        for mode in ("especes", "mobile_money", "assurance", "credit", "cheque"):
            val = qs.filter(mode_paiement=mode).aggregate(total=S("montant_total"))["total"] or 0
            repartition[mode] = str(val)

        # Top 10 produits sur la période
        top_produits = (
            LigneVente.objects
            .filter(vente__in=qs)
            .values("medicament__nom")
            .annotate(quantite_totale=Sum("quantite"), ca=Sum("montant_total"))
            .order_by("-ca")[:10]
        )

        return Response({
            "debut": str(debut),
            "fin": str(fin),
            "ca_total": str(agg["ca_total"] or 0),
            "nb_ventes": agg["nb_ventes"] or 0,
            "remises_total": str(agg["remises_total"] or 0),
            "repartition_paiement": repartition,
            "top_produits": list(top_produits),
        })

    # ── Top produits ──────────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="top-produits", permission_classes=[EstPharmacienAdjoint])
    def top_produits(self, request):
        """
        GET /api/rapports/top-produits/?periode=30&limit=20
        Retourne les médicaments les plus vendus sur `periode` jours.
        """
        from django.db.models import Sum
        try:
            from gestion.ventes.models import LigneVente
        except ImportError:
            return Response([], status=200)

        try:
            periode = int(request.query_params.get("periode", 30))
        except (ValueError, TypeError):
            periode = 30
        limit = min(int(request.query_params.get("limit", 20)), 100)

        debut = timezone.localdate() - timedelta(days=periode)
        qs = (
            LigneVente.objects
            .filter(vente__cree_le__date__gte=debut, vente__statut="validee")
            .values("medicament__id", "medicament__nom", "medicament__denomination_commune_internationale")
            .annotate(
                quantite_totale=Sum("quantite"),
                ca_total=Sum("montant_total"),
            )
            .order_by("-quantite_totale")[:limit]
        )
        return Response(list(qs))

    # ── Marges (réservé Titulaire) ────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="marges", permission_classes=[EstTitulaire])
    def marges(self, request):
        """
        GET /api/rapports/marges/?debut=&fin=&page=&page_size=
        Marge brute par produit — PAGINÉ pour éviter la matérialisation
        de toute la table Vente en mémoire (§rapport qualité).
        """
        from django.db.models import Sum, Avg
        try:
            from gestion.ventes.models import LigneVente
        except ImportError:
            return Response({"count": 0, "results": []}, status=200)

        today = timezone.localdate()
        debut_str = request.query_params.get("debut")
        fin_str   = request.query_params.get("fin")
        try:
            debut = date.fromisoformat(debut_str) if debut_str else today - timedelta(days=30)
            fin   = date.fromisoformat(fin_str)   if fin_str   else today
        except ValueError:
            debut = today - timedelta(days=30)
            fin = today

        # Bornage strict de la fenêtre (max 366 jours) pour éviter les full-scans.
        if (fin - debut).days > 366:
            return Response(
                {"detail": "Fenêtre trop large (max 366 jours)."}, status=400,
            )

        qs = (
            LigneVente.objects
            .filter(vente__cree_le__date__gte=debut, vente__cree_le__date__lte=fin, vente__statut="validee")
            .values("medicament__id", "medicament__nom")
            .annotate(
                quantite_totale=Sum("quantite"),
                ca_total=Sum("montant_total"),
                pa_moyen=Avg("lot__prix_achat_unitaire"),
            )
            .order_by("-ca_total")
        )

        # Pagination DRF standard — respecte PAGE_SIZE (25) et ?page_size=.
        # On passe le QuerySet directement pour laisser DRF borner la requête
        # SQL avant matérialisation en mémoire.
        page = self.paginate_queryset(qs)
        source = page if page is not None else qs

        def _rendre(r):
            ca = float(r["ca_total"] or 0)
            pa = float(r["pa_moyen"] or 0)
            qte = r["quantite_totale"] or 0
            marge_brute = ca - (pa * qte)
            taux_marge = (marge_brute / ca * 100) if ca > 0 else 0
            return {
                "medicament_id": str(r["medicament__id"]),
                "medicament_nom": r["medicament__nom"],
                "quantite_totale": qte,
                "ca_total": str(round(ca, 2)),
                "pa_moyen": str(round(pa, 2)),
                "marge_brute": str(round(marge_brute, 2)),
                "taux_marge_pct": str(round(taux_marge, 1)),
            }

        resultats = [_rendre(r) for r in source]
        if page is not None:
            return self.get_paginated_response(resultats)
        return Response({"count": len(resultats), "results": resultats})

    # ── Écarts d'inventaire ───────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="ecarts-inventaire", permission_classes=[EstPharmacienAdjoint])
    def ecarts_inventaire(self, request):
        """
        GET /api/rapports/ecarts-inventaire/
        Retourne les inventaires clôturés avec leurs écarts.
        """
        try:
            from gestion.stocks.models import MouvementStock
            qs = (
                MouvementStock.objects
                .filter(type_mouvement="ajustement_moins")
                .select_related("lot__medicament")
                .order_by("-cree_le")[:100]
            )
            resultats = [
                {
                    "id": str(m.id),
                    "lot_nom": m.lot_nom,
                    "medicament_nom": m.medicament_nom,
                    "quantite_ecart": -m.quantite,
                    "motif": m.motif,
                    "date": m.cree_le.isoformat(),
                }
                for m in qs
            ]
            return Response(resultats)
        except Exception as e:
            return Response({"detail": str(e)}, status=200)

    # ── Export CSV ventes ─────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="export-ventes", permission_classes=[EstPharmacienAdjoint])
    def export_ventes(self, request):
        """
        GET /api/rapports/export-ventes/?debut=&fin=
        Export CSV des ventes validées — FileResponse CSV (§4.9 CDC).
        Colonnes : date, numéro, produit, lot, quantité, prix unit, total, caissier
        """
        today = timezone.localdate()
        debut_str = request.query_params.get("debut")
        fin_str   = request.query_params.get("fin")
        try:
            debut = date.fromisoformat(debut_str) if debut_str else today - timedelta(days=30)
            fin   = date.fromisoformat(fin_str)   if fin_str   else today
        except ValueError:
            debut = today - timedelta(days=30)
            fin = today

        try:
            from gestion.ventes.models import LigneVente
        except ImportError:
            return HttpResponse("Module ventes indisponible.", content_type="text/plain", status=500)

        lignes = (
            LigneVente.objects
            .filter(
                vente__cree_le__date__gte=debut,
                vente__cree_le__date__lte=fin,
                vente__statut="validee",
            )
            .select_related("vente__vendeur", "medicament", "lot")
            .order_by("vente__cree_le")
            .iterator(chunk_size=500)   # streaming côté ORM
        )

        class _Echo:
            """Buffer conforme à l'interface `write` attendue par csv.writer."""
            def write(self, valeur):
                return valeur

        writer = csv.writer(_Echo(), delimiter=";")
        entete = [
            "Date", "Numéro vente", "Médicament", "DCI", "Lot",
            "Quantité", "Prix unitaire (FCFA)", "Remise %", "Total ligne (FCFA)",
            "Mode paiement", "Caissier",
        ]

        def _generateur():
            # BOM UTF-8 pour Excel, puis en-tête, puis flux.
            yield "\ufeff"
            yield writer.writerow(entete)
            for l in lignes:
                yield writer.writerow([
                    l.vente.cree_le.strftime("%d/%m/%Y %H:%M"),
                    l.vente.numero,
                    l.medicament.nom,
                    getattr(l.medicament, "denomination_commune_internationale", ""),
                    l.lot.numero_lot if l.lot else "",
                    l.quantite,
                    str(l.prix_unitaire),
                    str(l.taux_remise),
                    str(l.montant_total),
                    l.vente.mode_paiement,
                    l.vente.vendeur.nom_complet if l.vente.vendeur else "",
                ])

        response = StreamingHttpResponse(_generateur(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ventes_{debut}_{fin}.csv"'
        return response
