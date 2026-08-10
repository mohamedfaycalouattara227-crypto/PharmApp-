import uuid
import django.utils.timezone
from django.db import migrations, models
import infrastructure.outbox.modeles


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EntreeOutbox",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type_evenement", models.CharField(max_length=100, verbose_name="Type d'événement")),
                ("charge_utile", models.JSONField(default=dict, verbose_name="Charge utile (données)")),
                ("statut", models.CharField(
                    choices=[
                        ("en_attente", "En attente"),
                        ("en_cours", "En cours de traitement"),
                        ("traite", "Traité avec succès"),
                        ("echec", "Échec définitif"),
                    ],
                    default="en_attente", max_length=15, verbose_name="Statut",
                )),
                ("id_objet", models.UUIDField(blank=True, null=True, verbose_name="UUID de l'objet source")),
                ("modele_source", models.CharField(blank=True, max_length=100, verbose_name="Modèle Django source")),
                ("id_utilisateur", models.UUIDField(blank=True, null=True, verbose_name="Utilisateur ayant déclenché l'événement")),
                ("nombre_tentatives", models.PositiveSmallIntegerField(default=0, verbose_name="Nombre de tentatives")),
                ("max_tentatives", models.PositiveSmallIntegerField(default=5, verbose_name="Nombre maximum de tentatives")),
                ("prochaine_tentative", models.DateTimeField(blank=True, null=True, verbose_name="Date de la prochaine tentative")),
                ("erreur_message", models.TextField(blank=True, verbose_name="Message d'erreur (dernière tentative)")),
                ("cree_le", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("traite_le", models.DateTimeField(blank=True, null=True, verbose_name="Traité le")),
            ],
            options={
                "verbose_name": "Entrée Outbox",
                "verbose_name_plural": "Entrées Outbox",
                "db_table": "outbox_entrees",
                "ordering": ["cree_le"],
            },
        ),
        migrations.AddIndex(
            model_name="entreeoutbox",
            index=models.Index(fields=["statut", "prochaine_tentative"], name="outbox_statut_prochaine_idx"),
        ),
        migrations.AddIndex(
            model_name="entreeoutbox",
            index=models.Index(fields=["type_evenement", "statut"], name="outbox_type_statut_idx"),
        ),
        migrations.AddIndex(
            model_name="entreeoutbox",
            index=models.Index(fields=["cree_le"], name="outbox_cree_le_idx"),
        ),
    ]
