import uuid
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MouvementStock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mouvements", to="catalogue.lot")),
                ("type_mouvement", models.CharField(
                    choices=[
                        ("reception", "Réception fournisseur"),
                        ("vente", "Sortie vente"),
                        ("retour_client", "Retour client"),
                        ("ajustement_plus", "Ajustement positif (inventaire)"),
                        ("ajustement_moins", "Ajustement négatif (inventaire)"),
                        ("peremption", "Mise au rebut (périmé)"),
                        ("transfert_entree", "Transfert entrant"),
                        ("transfert_sortie", "Transfert sortant"),
                        ("perte", "Perte / vol constaté"),
                    ],
                    max_length=20,
                )),
                ("quantite", models.IntegerField(verbose_name="Quantité (positive=entrée, négative=sortie)")),
                ("quantite_avant", models.PositiveIntegerField(verbose_name="Stock avant mouvement")),
                ("quantite_apres", models.PositiveIntegerField(verbose_name="Stock après mouvement")),
                ("motif", models.TextField(blank=True)),
                ("reference_document", models.CharField(blank=True, max_length=100, verbose_name="Réf. document (n° vente, bon commande…)")),
                ("effectue_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mouvements_stock", to=settings.AUTH_USER_MODEL)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Mouvement de stock",
                "verbose_name_plural": "Mouvements de stock",
                "db_table": "stocks_mouvement",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="mouvementstock", index=models.Index(fields=["lot", "cree_le"], name="stock_lot_date_idx")),
        migrations.AddIndex(model_name="mouvementstock", index=models.Index(fields=["type_mouvement", "cree_le"], name="stock_type_date_idx")),
        migrations.CreateModel(
            name="AlerteStock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("medicament", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alertes_stock", to="catalogue.medicament")),
                ("niveau", models.CharField(choices=[("alerte", "Alerte (stock bas)"), ("rupture", "Rupture de stock")], max_length=10)),
                ("stock_au_moment_alerte", models.PositiveIntegerField()),
                ("seuil_depasse", models.PositiveIntegerField()),
                ("est_resolue", models.BooleanField(default=False)),
                ("resolue_le", models.DateTimeField(blank=True, null=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Alerte de stock",
                "verbose_name_plural": "Alertes de stock",
                "db_table": "stocks_alerte",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="alertestock", index=models.Index(fields=["est_resolue"], name="alerte_resolue_idx")),
        migrations.AddIndex(model_name="alertestock", index=models.Index(fields=["medicament"], name="alerte_med_idx")),
        migrations.CreateModel(
            name="Inventaire",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(max_length=50, unique=True)),
                ("statut", models.CharField(
                    choices=[("en_cours", "En cours"), ("termine", "Terminé"), ("valide", "Validé"), ("annule", "Annulé")],
                    default="en_cours", max_length=15,
                )),
                ("demarre_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventaires_demarre", to=settings.AUTH_USER_MODEL)),
                ("valide_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventaires_valides", to=settings.AUTH_USER_MODEL)),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("termine_le", models.DateTimeField(blank=True, null=True)),
                ("valide_le", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Inventaire",
                "verbose_name_plural": "Inventaires",
                "db_table": "stocks_inventaire",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.CreateModel(
            name="LigneInventaire",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("inventaire", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lignes", to="stocks.inventaire")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lignes_inventaire", to="catalogue.lot")),
                ("quantite_systeme", models.PositiveIntegerField(verbose_name="Quantité système")),
                ("quantite_comptee", models.PositiveIntegerField(verbose_name="Quantité comptée physiquement")),
                ("ecart", models.IntegerField(default=0, verbose_name="Écart (compté - système)")),
                ("ecart_pourcent", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=6)),
                ("notes", models.TextField(blank=True)),
                ("compte_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comptages_inventaire", to=settings.AUTH_USER_MODEL)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Ligne d'inventaire",
                "verbose_name_plural": "Lignes d'inventaire",
                "db_table": "stocks_ligne_inventaire",
            },
        ),
        migrations.AlterUniqueTogether(name="ligneinventaire", unique_together={("inventaire", "lot")}),
    ]
