"""
Migration initiale — App synchronisation.
Crée la table EvenementSync avec ses index d'interrogation.
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identite", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvenementSync",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        unique=True,
                        help_text="UUID généré côté serveur local. Garantit l'idempotence.",
                    ),
                ),
                (
                    "officine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="evenements_sync",
                        to="identite.officine",
                    ),
                ),
                (
                    "type_evenement",
                    models.CharField(
                        max_length=50,
                        help_text="Type d'événement — détermine le traitement appliqué.",
                    ),
                ),
                (
                    "version_schema",
                    models.PositiveSmallIntegerField(
                        default=1,
                        help_text="Version du schéma de charge_utile.",
                    ),
                ),
                (
                    "timestamp_local",
                    models.DateTimeField(
                        help_text="Horodatage de l'événement sur le serveur local.",
                    ),
                ),
                (
                    "recu_le",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="Horodatage de réception par le cloud.",
                    ),
                ),
                (
                    "charge_utile",
                    models.JSONField(
                        help_text="Corps de l'événement.",
                    ),
                ),
                (
                    "statut_traitement",
                    models.CharField(
                        choices=[
                            ("recu",     "Reçu"),
                            ("en_cours", "En cours de traitement"),
                            ("traite",   "Traité"),
                            ("echec",    "Échec"),
                            ("ignore",   "Ignoré (type inconnu)"),
                        ],
                        default="recu",
                        max_length=20,
                    ),
                ),
                ("traite_le",      models.DateTimeField(blank=True, null=True)),
                ("message_erreur", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Événement sync",
                "verbose_name_plural": "Événements sync",
                "ordering": ["-recu_le"],
                "app_label": "synchronisation",
            },
        ),
        migrations.AddIndex(
            model_name="evenementsync",
            index=models.Index(fields=["uuid"],                        name="sync_ev_uuid_idx"),
        ),
        migrations.AddIndex(
            model_name="evenementsync",
            index=models.Index(fields=["officine", "recu_le"],         name="sync_ev_off_recu_idx"),
        ),
        migrations.AddIndex(
            model_name="evenementsync",
            index=models.Index(fields=["officine", "type_evenement"],  name="sync_ev_off_type_idx"),
        ),
        migrations.AddIndex(
            model_name="evenementsync",
            index=models.Index(fields=["statut_traitement"],           name="sync_ev_statut_idx"),
        ),
        migrations.AddIndex(
            model_name="evenementsync",
            index=models.Index(fields=["timestamp_local"],             name="sync_ev_ts_local_idx"),
        ),
    ]
