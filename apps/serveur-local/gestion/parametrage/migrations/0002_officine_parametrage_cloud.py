"""
Migration 0002 — Ajout du modèle OfficineParametrage (connexion Cloud PharmApp).

Non-destructive : ajout d'une nouvelle table. Aucune colonne existante n'est modifiée.
"""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametrage", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficineParametrage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        default=uuid.UUID("00000000-0000-0000-0000-000000000099"),
                        editable=False,
                        serialize=False,
                    ),
                ),
                (
                    "officine_id",
                    models.UUIDField(
                        blank=True,
                        null=True,
                        help_text="UUID attribué par le cloud lors du provisionnement.",
                    ),
                ),
                (
                    "code_officine",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        help_text='Code court de la pharmacie côté cloud (ex: "PHA-001").',
                    ),
                ),
                (
                    "cloud_api_url",
                    models.URLField(
                        blank=True,
                        help_text="URL de base de l'API cloud.",
                    ),
                ),
                (
                    "cle_api_chiffree",
                    models.TextField(
                        blank=True,
                        help_text="Clé API chiffrée AES-256-GCM. Ne jamais modifier manuellement.",
                    ),
                ),
                (
                    "prefixe_cle",
                    models.CharField(
                        blank=True,
                        max_length=12,
                        help_text='Préfixe non-secret ("phk_XXXX") pour vérification visuelle.',
                    ),
                ),
                ("configure_le",     models.DateTimeField(blank=True, null=True)),
                ("modifie_le",       models.DateTimeField(auto_now=True)),
                (
                    "version_logiciel",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        help_text="Version du logiciel local.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Paramétrage Cloud",
                "db_table": "parametrage_officine_cloud",
                "app_label": "parametrage",
            },
        ),
    ]
