"""
Migration initiale — App identite.
Crée la table Officine avec tous ses index.
"""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Officine",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Identifiant unique de l'officine, communiqué au serveur local.",
                    ),
                ),
                ("nom",   models.CharField(max_length=200)),
                ("code",  models.CharField(max_length=20, unique=True)),
                ("ville", models.CharField(blank=True, max_length=100)),
                ("pays",  models.CharField(default="Burkina Faso", max_length=100)),
                (
                    "cle_api_hash",
                    models.CharField(
                        max_length=128,
                        help_text="SHA-256 hexadécimal de la clé API — jamais la clé en clair.",
                    ),
                ),
                (
                    "cle_api_prefixe",
                    models.CharField(
                        max_length=12,
                        help_text="Préfixe non-secret de la clé (ex: 'phk_A1B2') pour identification.",
                    ),
                ),
                (
                    "statut_abonnement",
                    models.CharField(
                        choices=[
                            ("essai",    "Essai"),
                            ("actif",    "Actif"),
                            ("suspendu", "Suspendu"),
                            ("expire",   "Expiré"),
                        ],
                        default="essai",
                        max_length=20,
                    ),
                ),
                ("date_debut_abonnement", models.DateField(blank=True, null=True)),
                ("date_fin_abonnement",   models.DateField(blank=True, null=True)),
                ("version_logiciel",   models.CharField(blank=True, max_length=20)),
                ("derniere_connexion", models.DateTimeField(blank=True, null=True)),
                ("est_active",   models.BooleanField(default=True)),
                ("cree_le",      models.DateTimeField(auto_now_add=True)),
                ("mis_a_jour_le",models.DateTimeField(auto_now=True)),
                ("notes",        models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Officine",
                "verbose_name_plural": "Officines",
                "ordering": ["code"],
                "app_label": "identite",
            },
        ),
        migrations.AddIndex(
            model_name="officine",
            index=models.Index(fields=["cle_api_hash"],       name="identite_of_cle_api_hash_idx"),
        ),
        migrations.AddIndex(
            model_name="officine",
            index=models.Index(fields=["statut_abonnement"],  name="identite_of_statut_abo_idx"),
        ),
        migrations.AddIndex(
            model_name="officine",
            index=models.Index(fields=["derniere_connexion"], name="identite_of_derniere_cnx_idx"),
        ),
    ]
