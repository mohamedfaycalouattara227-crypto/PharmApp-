"""
gestion/produits_controles/vues.py — Étape 13

Vues DRF pour le registre des produits contrôlés (stupéfiants, psychotropes).

Ajouts étape 13 :
  - action export_registre : GET .../export-registre/ → PDF réglementaire
  - Filtres : par médicament, par période (date_debut, date_fin)
  - Accès : pharmacien_adjoint minimum (caissier ne peut PAS voir ce registre)
  - DELETE interdit (obligation légale de traçabilité)
"""

import io
import logging
from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import EstPharmacienAdjoint

logger = logging.getLogger("pharmapp.produits_controles")


class VueProduitControle(viewsets.ModelViewSet):
    """
    Registre réglementaire des produits contrôlés.
    Toute opération est journalisée en CRITIQUE.

    Règles d'accès :
      - GET (liste, détail) : pharmacien_adjoint minimum
      - POST (création) : pharmacien_adjoint minimum
      - PUT/PATCH (modification) : interdit via API (immuabilité réglementaire)
      - DELETE : interdit (HTTP 405 explicite)

    Filtres disponibles :
      ?medicament=<uuid>
      ?date_debut=YYYY-MM-DD
      ?date_fin=YYYY-MM-DD
      ?type_mouvement=sortie_vente|entree|retour|...
    """

    permission_classes = [EstPharmacienAdjoint]

    def get_queryset(self):
        from gestion.produits_controles.models import RegistreProduitControle
        qs = (
            RegistreProduitControle.objects
            .select_related(
                "medicament", "lot", "ordonnance",
                "effectue_par", "supervise_par",
            )
            .order_by("-cree_le")
        )

        # Filtres
        medicament_id = self.request.query_params.get("medicament")
        if medicament_id:
            qs = qs.filter(medicament_id=medicament_id)

        date_debut = self.request.query_params.get("date_debut")
        if date_debut:
            qs = qs.filter(cree_le__date__gte=date_debut)

        date_fin = self.request.query_params.get("date_fin")
        if date_fin:
            qs = qs.filter(cree_le__date__lte=date_fin)

        type_mvt = self.request.query_params.get("type_mouvement")
        if type_mvt:
            qs = qs.filter(type_mouvement=type_mvt)

        return qs

    def get_serializer_class(self):
        from gestion.produits_controles.serialiseurs import RegistreProduitControleSerialiseur
        return RegistreProduitControleSerialiseur

    def destroy(self, request, *args, **kwargs):
        """
        Suppression physique interdite — obligation réglementaire de traçabilité.
        Retourne HTTP 405 avec un message explicite.
        """
        return Response(
            {
                "detail": (
                    "La suppression d'un enregistrement de produit contrôlé est interdite. "
                    "Les registres stupéfiants/psychotropes doivent être conservés sans "
                    "modification ni effacement (obligation légale de traçabilité). "
                    "Pour signaler une erreur d'enregistrement, contactez le titulaire."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        """Modification interdite — registre immuable."""
        return Response(
            {"detail": "Le registre des produits contrôlés est immuable."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        """Modification partielle interdite — registre immuable."""
        return Response(
            {"detail": "Le registre des produits contrôlés est immuable."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="export-registre",
        permission_classes=[EstPharmacienAdjoint],
    )
    def export_registre(self, request):
        """
        Exporte le registre des produits contrôlés au format PDF.
        GET /api/produits-controles/export-registre/
            ?date_debut=YYYY-MM-DD
            &date_fin=YYYY-MM-DD
            &medicament=<uuid>

        Format réglementaire ANRP (Burkina Faso) :
          - Colonne date, produit, acheteur, ordonnance, quantité, vendeur
          - En-tête : nom pharmacie, numéro d'agrément, période
          - Numérotation des pages
        """
        from django.http import HttpResponse
        from gestion.parametrage.models import Parametrage

        # Récupérer les entrées filtrées
        qs = self.get_queryset()

        # Période
        date_debut_str = request.query_params.get("date_debut", "")
        date_fin_str = request.query_params.get("date_fin", "")

        # Paramétrage pharmacie
        try:
            param = Parametrage.obtenir()
            nom_pharmacie = param.nom_pharmacie
            numero_agrement = param.numero_agrement
        except Exception as exc:
            logger.warning("Impossible de lire le paramétrage pour l'export registre : %s", exc)
            nom_pharmacie = "Pharmacie"
            numero_agrement = "—"

        # Génération PDF avec reportlab
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=1.5 * cm,
                leftMargin=1.5 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
                title=f"Registre Produits Contrôlés — {nom_pharmacie}",
            )

            styles = getSampleStyleSheet()
            style_titre = ParagraphStyle(
                "titre", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=14
            )
            style_sous_titre = ParagraphStyle(
                "sous_titre", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10
            )
            style_normal = ParagraphStyle(
                "normal_small", parent=styles["Normal"], fontSize=7
            )

            elements = []

            # En-tête
            elements.append(Paragraph(f"REGISTRE DES PRODUITS CONTRÔLÉS", style_titre))
            elements.append(Paragraph(nom_pharmacie, style_sous_titre))
            if numero_agrement:
                elements.append(Paragraph(f"Agrément N° {numero_agrement}", style_sous_titre))
            periode = ""
            if date_debut_str or date_fin_str:
                periode = f"Période : {date_debut_str or '…'} → {date_fin_str or '…'}"
            else:
                periode = f"Export complet au {date.today().strftime('%d/%m/%Y')}"
            elements.append(Paragraph(periode, style_sous_titre))
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
            elements.append(Spacer(1, 0.3 * cm))

            # En-têtes du tableau
            entetes = [
                "Date", "Mouvement", "Produit", "Lot",
                "Qté", "Acheteur / Patient", "Ordonnance",
                "Prescripteur", "Vendeur",
            ]

            donnees = [entetes]
            for entree in qs:
                # Déchiffrer le nom patient
                try:
                    patient = entree.patient_nom or "—"
                except Exception as exc:
                    logger.warning("Déchiffrement patient_nom échoué pour registre id=%s : %s", entree.id, type(exc).__name__)
                    patient = "—"

                ordonnance_ref = (
                    entree.ordonnance.numero_interne
                    if entree.ordonnance
                    else "—"
                )

                donnees.append([
                    entree.cree_le.strftime("%d/%m/%Y %H:%M"),
                    entree.get_type_mouvement_display(),
                    entree.medicament.nom[:30],
                    entree.numero_lot_fabricant or "—",
                    f"{entree.quantite_mouvement} {entree.unite}",
                    patient[:25],
                    ordonnance_ref[:15],
                    (entree.prescripteur_nom or "—")[:20],
                    entree.effectue_par.nom_complet[:20],
                ])

            # Tableau
            col_widths = [
                2.5 * cm, 2.5 * cm, 3.5 * cm, 2 * cm,
                1.5 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm,
            ]

            table = Table(donnees, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                # En-tête
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                # Corps
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 6.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fc")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(table)

            # Pied de page — nombre d'entrées
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(
                Paragraph(
                    f"Total : {qs.count()} enregistrement(s). "
                    f"Document généré le {date.today().strftime('%d/%m/%Y')} par "
                    f"{request.user.nom_complet}.",
                    style_normal,
                )
            )

            doc.build(elements)
            buffer.seek(0)

            nom_fichier = (
                f"registre_produits_controles_{date.today().strftime('%Y%m%d')}.pdf"
            )
            response = HttpResponse(buffer.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
            return response

        except ImportError:
            # Fallback : export CSV si reportlab indisponible
            import csv
            from django.http import HttpResponse as HR

            response = HR(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                'attachment; filename="registre_produits_controles.csv"'
            )
            writer = csv.writer(response, delimiter=";")
            writer.writerow([
                "Date", "Mouvement", "Produit", "Lot", "Quantité",
                "Acheteur", "Ordonnance", "Prescripteur", "Vendeur",
            ])
            for entree in qs:
                try:
                    patient = entree.patient_nom or ""
                except Exception as exc:
                    logger.warning("Déchiffrement patient_nom échoué pour CSV id=%s : %s", entree.id, type(exc).__name__)
                    patient = ""
                writer.writerow([
                    entree.cree_le.strftime("%d/%m/%Y %H:%M"),
                    entree.get_type_mouvement_display(),
                    entree.medicament.nom,
                    entree.numero_lot_fabricant or "",
                    f"{entree.quantite_mouvement} {entree.unite}",
                    patient,
                    entree.ordonnance.numero_interne if entree.ordonnance else "",
                    entree.prescripteur_nom or "",
                    entree.effectue_par.nom_complet,
                ])
            return response
