# Generated manually — ajout CompteurNumerotation (fix race-condition numérotation)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametrage", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompteurNumerotation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("vente", "Vente"),
                            ("bon_commande", "Bon de commande"),
                        ],
                        max_length=20,
                    ),
                ),
                ("annee", models.PositiveSmallIntegerField()),
                ("sequence", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Compteur de numérotation",
                "db_table": "parametrage_compteur_numerotation",
                "unique_together": {("type", "annee")},
            },
        ),
    ]
