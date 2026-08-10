from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventes", "0003_vente_avoir_et_mobile_money"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="lignevente",
            table="ventes_ligne_vente",
        ),
        migrations.RenameField(
            model_name="lignevente",
            old_name="montant_ligne",
            new_name="montant_total",
        ),
        migrations.RemoveField(
            model_name="lignevente",
            name="cree_le",
        ),
        migrations.AlterField(
            model_name="lignevente",
            name="lot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lignes_vente",
                to="catalogue.lot",
            ),
        ),
        migrations.AlterField(
            model_name="lignevente",
            name="prix_unitaire",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name="lignevente",
            name="prix_unitaire_apres_remise",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="vente",
            name="reference_mobile_money",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Numéro de confirmation Orange Money / Moov Money. "
                    "Obligatoire si mode_paiement=mobile_money."
                ),
                max_length=100,
                verbose_name="Référence transaction Mobile Money",
            ),
        ),
        migrations.AlterField(
            model_name="vente",
            name="vente_origine",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="avoirs",
                to="ventes.vente",
                verbose_name="Vente d'origine (avoirs uniquement)",
            ),
        ),
        migrations.AlterField(
            model_name="cloturecaisse",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_cours", "En cours"),
                    ("cloturee", "Clôturée"),
                    ("validee", "Validée"),
                ],
                default="en_cours",
                max_length=15,
            ),
        ),
        migrations.AddIndex(
            model_name="vente",
            index=models.Index(fields=["client", "statut"], name="vente_client_statut_idx"),
        ),
        migrations.AlterField(
            model_name="vente",
            name="annule_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ventes_annulees",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
