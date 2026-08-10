import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EtatSynchronisation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("statut_connexion", models.CharField(
                    choices=[("en_ligne", "En ligne"), ("hors_ligne", "Hors ligne"), ("degradee", "Connexion dégradée")],
                    default="hors_ligne", max_length=15,
                )),
                ("derniere_sync_reussie", models.DateTimeField(blank=True, null=True)),
                ("derniere_tentative", models.DateTimeField(blank=True, null=True)),
                ("nombre_evenements_en_attente", models.PositiveIntegerField(default=0)),
                ("nombre_evenements_en_echec", models.PositiveIntegerField(default=0)),
                ("nombre_conflits_non_resolus", models.PositiveIntegerField(default=0)),
                ("message_statut", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "État de synchronisation",
                "verbose_name_plural": "États de synchronisation",
                "db_table": "synchronisation_etat",
                "ordering": ["-modifie_le"],
            },
        ),
        migrations.CreateModel(
            name="ConflitSynchronisation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("modele", models.CharField(max_length=100, verbose_name="Modèle Django concerné")),
                ("id_objet", models.UUIDField(verbose_name="UUID de l'objet en conflit")),
                ("donnees_locales", models.JSONField(verbose_name="Version locale")),
                ("donnees_cloud", models.JSONField(verbose_name="Version cloud")),
                ("statut", models.CharField(
                    choices=[
                        ("non_resolu", "Non résolu"),
                        ("resolu_local", "Résolu — version locale conservée"),
                        ("resolu_cloud", "Résolu — version cloud appliquée"),
                        ("ignore", "Ignoré"),
                    ],
                    default="non_resolu", max_length=20,
                )),
                ("resolu_par", models.CharField(blank=True, max_length=50)),
                ("resolu_le", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Conflit de synchronisation",
                "verbose_name_plural": "Conflits de synchronisation",
                "db_table": "synchronisation_conflit",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AlterUniqueTogether(name="conflitsynchronisation", unique_together={("modele", "id_objet", "statut")}),
        migrations.AddIndex(model_name="conflitsynchronisation", index=models.Index(fields=["statut"], name="sync_statut_idx")),
        migrations.AddIndex(model_name="conflitsynchronisation", index=models.Index(fields=["modele", "id_objet"], name="sync_modele_obj_idx")),
    ]
