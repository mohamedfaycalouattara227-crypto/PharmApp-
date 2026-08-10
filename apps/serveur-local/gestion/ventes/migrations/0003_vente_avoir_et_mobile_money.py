"""
Migration : Étape 14 + Étape 11
  - Ajoute StatutVente.AVOIR
  - Ajoute Vente.vente_origine (FK self, null=True)
  - Ajoute Vente.reference_mobile_money (CharField, blank=True)
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0002_vente_nb_impressions"),
    ]

    operations = [
        # Étendre le champ statut pour inclure 'avoir'
        migrations.AlterField(
            model_name="vente",
            name="statut",
            field=models.CharField(
                choices=[
                    ("en_cours", "En cours"),
                    ("validee", "Validée"),
                    ("annulee", "Annulée"),
                    ("avoir", "Avoir (note de crédit)"),
                ],
                default="validee",
                max_length=20,
            ),
        ),
        # FK vente_origine pour les avoirs
        migrations.AddField(
            model_name="vente",
            name="vente_origine",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="avoirs",
                to="ventes.vente",
                verbose_name="Vente d'origine (pour les avoirs)",
            ),
        ),
        # Référence Mobile Money
        migrations.AddField(
            model_name="vente",
            name="reference_mobile_money",
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name="Référence transaction Mobile Money",
                help_text="Numéro de confirmation Orange Money / Moov Money.",
            ),
        ),
    ]
