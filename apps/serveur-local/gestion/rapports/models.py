"""
gestion/rapports/models.py
Modèle RapportGenere — rapports périodiques pré-calculés.
"""

import uuid
from django.conf import settings
from django.db import models


class TypeRapport(models.TextChoices):
    VENTES_JOURNALIER  = "ventes_journalier",  "Ventes journalières"
    VENTES_MENSUEL     = "ventes_mensuel",     "Ventes mensuelles"
    MARGES             = "marges",             "Marges par médicament"
    PEREMPTIONS        = "peremptions",        "Médicaments proches péremption"
    MOUVEMENTS_STOCK   = "mouvements_stock",   "Mouvements de stock"
    PRODUITS_CONTROLES = "produits_controles", "Produits contrôlés"
    CLIENTS_CREDIT     = "clients_credit",     "Créances clients"
    ACTIVITE_CAISSE    = "activite_caisse",    "Activité de caisse"


class RapportGenere(models.Model):
    """Rapport pré-calculé et mis en cache pour consultation rapide."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_rapport = models.CharField(max_length=30, choices=TypeRapport.choices)
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    titre = models.CharField(max_length=200)
    donnees = models.JSONField(default=dict)
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="rapports_generes",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rapports_rapport"
        verbose_name = "Rapport"
        verbose_name_plural = "Rapports"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["type_rapport", "cree_le"], name="idx_rapport_type_cree_le"),
            models.Index(
                fields=["periode_debut", "periode_fin"], name="idx_rapport_periode"
            ),
        ]

    def __str__(self):
        return f"{self.titre} ({self.periode_debut} → {self.periode_fin})"
