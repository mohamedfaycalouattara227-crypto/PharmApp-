"""
Migration 0002 : ajout du champ allergies sur le modèle Client (étape 5 — CDC §4.6 §7.2).

allergies : données médicales sensibles — visibles uniquement par les rôles
            pharmacien_adjoint (niveau 4) et supérieurs.
            Un caissier ne doit JAMAIS voir ce champ (restriction côté serializer serveur).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="allergies",
            field=models.TextField(
                blank=True,
                verbose_name="Allergies connues",
                help_text=(
                    "Données médicales sensibles. "
                    "Visibles uniquement par pharmacien_adjoint et supérieurs (§7.2 CDC)."
                ),
            ),
        ),
    ]
