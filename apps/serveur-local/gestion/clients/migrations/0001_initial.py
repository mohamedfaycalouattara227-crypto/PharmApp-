import uuid
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom", models.CharField(max_length=150, verbose_name="Nom")),
                ("prenom", models.CharField(blank=True, max_length=150, verbose_name="Prénom")),
                ("telephone", models.CharField(blank=True, max_length=25, unique=True, verbose_name="Téléphone")),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("date_naissance", models.DateField(blank=True, null=True)),
                ("adresse", models.TextField(blank=True)),
                ("type_client", models.CharField(
                    choices=[
                        ("particulier", "Particulier"),
                        ("assurance", "Assurance / Mutuelle"),
                        ("institution", "Institution (hôpital, ONG…)"),
                    ],
                    default="particulier",
                    max_length=20,
                )),
                ("assureur", models.CharField(blank=True, max_length=200)),
                ("numero_assurance", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("taux_prise_en_charge", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5, verbose_name="Taux de prise en charge (%)")),
                ("credit_autorise", models.BooleanField(default=False, verbose_name="Crédit autorisé")),
                ("plafond_credit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10, verbose_name="Plafond de crédit (FCFA)")),
                ("est_actif", models.BooleanField(default=True)),
                ("est_anonymise", models.BooleanField(default=False, verbose_name="Données anonymisées (RGPD)")),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Client",
                "verbose_name_plural": "Clients",
                "db_table": "clients_client",
                "ordering": ["nom", "prenom"],
            },
        ),
        migrations.AddIndex(
            model_name="client",
            index=models.Index(fields=["telephone"], name="cli_tel_idx"),
        ),
        migrations.AddIndex(
            model_name="client",
            index=models.Index(fields=["est_actif"], name="cli_actif_idx"),
        ),
    ]
