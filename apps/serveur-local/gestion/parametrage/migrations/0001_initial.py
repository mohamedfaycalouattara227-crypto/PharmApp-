"""Migration initiale — création de la table parametrage (singleton)."""

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="Parametrage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        default=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                        editable=False,
                        serialize=False,
                    ),
                ),
                ("nom_pharmacie",   models.CharField(default="Pharmacie", max_length=200)),
                ("adresse",         models.TextField(blank=True)),
                ("telephone",       models.CharField(blank=True, max_length=30)),
                ("email",           models.EmailField(blank=True, max_length=254)),
                ("ville",           models.CharField(default="Bobo-Dioulasso", max_length=100)),
                ("numero_agrement", models.CharField(blank=True, max_length=100)),
                (
                    "logo",
                    models.ImageField(blank=True, null=True, upload_to="parametrage/logos/"),
                ),
                ("devise",              models.CharField(default="FCFA", max_length=10)),
                ("format_numerotation", models.CharField(default="VTE-{YYYY}-{NNNN}", max_length=50)),
                ("seuil_alerte_stock_jours", models.PositiveIntegerField(default=20)),
                ("seuil_peremption_jours",   models.PositiveIntegerField(default=60)),
                (
                    "type_imprimante",
                    models.CharField(
                        choices=[("thermique", "Thermique 80 mm"), ("a4", "Feuille A4")],
                        default="thermique",
                        max_length=20,
                    ),
                ),
                ("timeout_inactivite_minutes",  models.PositiveIntegerField(default=30)),
                ("nb_tentatives_connexion_max", models.PositiveIntegerField(default=5)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Paramétrage",
                "db_table": "parametrage",
            },
        ),
    ]
