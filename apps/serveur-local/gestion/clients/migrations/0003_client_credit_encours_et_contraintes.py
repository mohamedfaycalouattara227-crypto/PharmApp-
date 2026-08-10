from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0002_client_allergies"),
    ]

    operations = [
        migrations.AlterField(
            model_name="client",
            name="telephone",
            field=models.CharField(
                blank=True,
                max_length=25,
                null=True,
                unique=True,
                verbose_name="Téléphone",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="encours_credit",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=10,
                verbose_name="Encours crédit actuel (FCFA)",
            ),
        ),
        migrations.AddIndex(
            model_name="client",
            index=models.Index(fields=["numero_assurance"], name="cli_num_ass_idx"),
        ),
    ]
