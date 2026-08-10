"""Rend le client facultatif sur une ordonnance.

Au comptoir, l'ordonnance est numérisée avant que le client ne soit identifié
(ou pour un client de passage). Le rattachement se fait ensuite lors de la
vente. La contrainte NOT NULL bloquait ce flux métier.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0001_initial"),
        ("ordonnances", "0003_index_ordonnances"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ordonnance",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ordonnances",
                to="clients.client",
                verbose_name="Client",
            ),
        ),
    ]
