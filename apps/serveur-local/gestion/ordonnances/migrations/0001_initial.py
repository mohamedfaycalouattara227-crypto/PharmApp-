import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ordonnance",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("numero_interne", models.CharField(max_length=50, unique=True, verbose_name="Numéro interne")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ordonnances", to="clients.client", verbose_name="Client")),
                ("prescripteur_nom", models.CharField(max_length=200, verbose_name="Nom du médecin prescripteur")),
                ("prescripteur_etablissement", models.CharField(blank=True, max_length=300, verbose_name="Établissement de santé")),
                ("date_prescription", models.DateField(verbose_name="Date de prescription")),
                ("date_expiration", models.DateField(blank=True, null=True, verbose_name="Date d'expiration")),
                ("image_chiffree", models.BinaryField(blank=True, null=True, verbose_name="Image chiffrée (AES-256-GCM)")),
                ("vecteur_initialisation", models.BinaryField(blank=True, null=True, verbose_name="Vecteur d'initialisation AES")),
                ("type_mime", models.CharField(blank=True, default="image/jpeg", max_length=50, verbose_name="Type MIME de l'image originale")),
                ("taille_image_octets", models.PositiveIntegerField(default=0)),
                ("statut", models.CharField(
                    choices=[
                        ("en_attente", "En attente de vérification"),
                        ("validee", "Validée par pharmacien"),
                        ("utilisee", "Utilisée (dispensée)"),
                        ("refusee", "Refusée"),
                        ("expiree", "Expirée (> 3 mois)"),
                    ],
                    default="en_attente", max_length=20,
                )),
                ("validee_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ordonnances_validees", to=settings.AUTH_USER_MODEL)),
                ("validee_le", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("numerisee_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ordonnances_numerisees", to=settings.AUTH_USER_MODEL)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Ordonnance",
                "verbose_name_plural": "Ordonnances",
                "db_table": "ordonnances_ordonnance",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="ordonnance", index=models.Index(fields=["client", "statut"], name="ord_client_statut_idx")),
        migrations.AddIndex(model_name="ordonnance", index=models.Index(fields=["statut"], name="ord_statut_idx")),
    ]
