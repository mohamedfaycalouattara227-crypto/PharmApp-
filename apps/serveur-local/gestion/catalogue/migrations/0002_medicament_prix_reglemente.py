"""
Migration 0002 : ajout des champs prix_reglemente, prix_reference, hors_nomenclature
sur le modèle Medicament (étape 4 — CDC §4.2).

prix_reglemente  : booléen — si True, le prix de vente est plafonné par prix_reference.
prix_reference   : plafond légal CAMEG/OHADA (nullable — obligatoire uniquement si prix_reglemente).
hors_nomenclature: flag pour les produits absents du référentiel national (prix libre).

La categorie devient nullable pour éviter des migrations de données complexes.
"""

from decimal import Decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="medicament",
            name="categorie",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="medicaments",
                to="catalogue.categorieproduit",
                verbose_name="Catégorie",
            ),
        ),
        migrations.AlterField(
            model_name="medicament",
            name="prix_public",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=10,
                verbose_name="Prix public (FCFA)",
            ),
        ),
        migrations.AddField(
            model_name="medicament",
            name="prix_reglemente",
            field=models.BooleanField(
                default=False,
                help_text="Si True, le prix de vente ne peut pas dépasser prix_reference.",
                verbose_name="Prix réglementé (CAMEG/OHADA)",
            ),
        ),
        migrations.AddField(
            model_name="medicament",
            name="prix_reference",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Plafond légal, obligatoire si prix_reglemente=True.",
                max_digits=10,
                null=True,
                verbose_name="Prix de référence réglementé (FCFA)",
            ),
        ),
        migrations.AddField(
            model_name="medicament",
            name="hors_nomenclature",
            field=models.BooleanField(
                default=False,
                help_text="Produit absent du référentiel CAMEG — prix libre sans plafond.",
                verbose_name="Hors nomenclature nationale",
            ),
        ),
    ]
