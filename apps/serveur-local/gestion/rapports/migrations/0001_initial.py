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
            name="RapportGenere",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type_rapport", models.CharField(
                    choices=[
                        ("ventes_journalier", "Ventes journalières"),
                        ("ventes_mensuel", "Ventes mensuelles"),
                        ("marges", "Marges par médicament"),
                        ("peremptions", "Médicaments proches péremption"),
                        ("mouvements_stock", "Mouvements de stock"),
                        ("produits_controles", "Produits contrôlés"),
                        ("clients_credit", "Créances clients"),
                        ("activite_caisse", "Activité de caisse"),
                    ],
                    max_length=30,
                )),
                ("periode_debut", models.DateField()),
                ("periode_fin", models.DateField()),
                ("titre", models.CharField(max_length=200)),
                ("donnees", models.JSONField(default=dict)),
                ("genere_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rapports_generes", to=settings.AUTH_USER_MODEL)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Rapport",
                "verbose_name_plural": "Rapports",
                "db_table": "rapports_rapport",
                "ordering": ["-cree_le"],
            },
        ),
    ]
