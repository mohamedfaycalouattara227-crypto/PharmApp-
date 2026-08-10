import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EcritureComptable",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type_ecriture", models.CharField(
                    choices=[
                        ("recette", "Recette"), ("depense", "Dépense"),
                        ("achat", "Achat fournisseur"), ("salaire", "Charge salariale"),
                        ("remise", "Remise accordée"), ("credit", "Créance client"),
                        ("recouvrement", "Recouvrement créance"),
                    ],
                    max_length=20,
                )),
                ("montant", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="Montant (FCFA)")),
                ("description", models.TextField()),
                ("reference_document", models.CharField(blank=True, max_length=100, verbose_name="Référence (n° vente, facture fournisseur…)")),
                ("id_vente", models.UUIDField(blank=True, null=True)),
                ("id_cloture", models.UUIDField(blank=True, null=True)),
                ("saisie_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ecritures_comptables", to=settings.AUTH_USER_MODEL)),
                ("date_ecriture", models.DateField()),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Écriture comptable",
                "verbose_name_plural": "Écritures comptables",
                "db_table": "comptabilite_ecriture",
                "ordering": ["-date_ecriture", "-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="ecriturecomptable", index=models.Index(fields=["date_ecriture"], name="compta_date_idx")),
        migrations.AddIndex(model_name="ecriturecomptable", index=models.Index(fields=["type_ecriture", "date_ecriture"], name="compta_type_date_idx")),
    ]
