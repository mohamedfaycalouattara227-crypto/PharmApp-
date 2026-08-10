import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("produits_controles", "0001_initial"),
        ("ventes", "0003_vente_avoir_et_mobile_money"),
    ]

    operations = [
        migrations.AddField(
            model_name="registreproduitcontrole",
            name="ligne_vente",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entree_registre_controle",
                to="ventes.lignevente",
                verbose_name="Ligne de vente d'origine",
            ),
        ),
        migrations.AddField(
            model_name="registreproduitcontrole",
            name="cree_par_reconciliation",
            field=models.BooleanField(default=False),
        ),
    ]
