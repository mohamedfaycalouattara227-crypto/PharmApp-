import uuid
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CategorieProduit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom", models.CharField(max_length=150, unique=True, verbose_name="Nom")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                ("code", models.CharField(blank=True, max_length=20, unique=True, verbose_name="Code")),
                ("est_active", models.BooleanField(default=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Catégorie",
                "verbose_name_plural": "Catégories",
                "db_table": "catalogue_categorie",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="Medicament",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nom", models.CharField(max_length=250, verbose_name="Nom commercial")),
                ("denomination_commune_internationale", models.CharField(blank=True, max_length=250, verbose_name="DCI")),
                ("code_cis", models.CharField(blank=True, max_length=50, unique=True, verbose_name="Code CIS (identifiant unique)")),
                ("code_barre", models.CharField(blank=True, max_length=50)),
                ("categorie", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="medicaments", to="catalogue.categorieproduit", verbose_name="Catégorie")),
                ("forme_pharmaceutique", models.CharField(blank=True, max_length=100, verbose_name="Forme (comprimé, sirop, injectable…)")),
                ("dosage", models.CharField(blank=True, max_length=100, verbose_name="Dosage")),
                ("conditionnement", models.CharField(blank=True, max_length=100, verbose_name="Conditionnement (boîte de 12, etc.)")),
                ("fabricant", models.CharField(blank=True, max_length=200)),
                ("pays_origine", models.CharField(blank=True, max_length=100)),
                ("prix_public", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Prix public (FCFA)")),
                ("prix_min_autorise", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10, verbose_name="Prix minimum autorisé")),
                ("prix_max_autorise", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10, verbose_name="Prix maximum autorisé")),
                ("taux_remise_max", models.DecimalField(decimal_places=2, default=Decimal("10.00"), max_digits=5, verbose_name="Remise maximale autorisée (%)")),
                ("necessite_ordonnance", models.BooleanField(default=False, verbose_name="Médicament sur ordonnance")),
                ("est_produit_controle", models.BooleanField(default=False, verbose_name="Stupéfiant / psychotrope")),
                ("est_actif", models.BooleanField(default=True, verbose_name="Actif dans le catalogue")),
                ("seuil_alerte_stock", models.PositiveIntegerField(default=20, verbose_name="Seuil d'alerte de stock (unités)")),
                ("seuil_rupture_stock", models.PositiveIntegerField(default=5, verbose_name="Seuil de rupture de stock (unités)")),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Médicament",
                "verbose_name_plural": "Médicaments",
                "db_table": "catalogue_medicament",
                "ordering": ["nom"],
            },
        ),
        migrations.AddIndex(
            model_name="medicament",
            index=models.Index(fields=["nom"], name="cat_med_nom_idx"),
        ),
        migrations.AddIndex(
            model_name="medicament",
            index=models.Index(fields=["code_cis"], name="cat_med_cis_idx"),
        ),
        migrations.AddIndex(
            model_name="medicament",
            index=models.Index(fields=["est_actif"], name="cat_med_actif_idx"),
        ),
        migrations.CreateModel(
            name="Lot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("medicament", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="catalogue.medicament", verbose_name="Médicament")),
                ("numero_lot", models.CharField(max_length=100, verbose_name="Numéro de lot fabricant")),
                ("numero_lot_interne", models.CharField(blank=True, max_length=50, unique=True, verbose_name="Référence interne")),
                ("date_fabrication", models.DateField(blank=True, null=True)),
                ("date_peremption", models.DateField(verbose_name="Date de péremption")),
                ("quantite_initiale", models.PositiveIntegerField(verbose_name="Quantité réceptionnée")),
                ("quantite_disponible", models.PositiveIntegerField(verbose_name="Quantité disponible")),
                ("prix_achat_unitaire", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Prix d'achat unitaire (FCFA)")),
                ("fournisseur", models.CharField(blank=True, max_length=200)),
                ("bon_commande", models.CharField(blank=True, max_length=100)),
                ("emplacement_stockage", models.CharField(blank=True, max_length=100, verbose_name="Emplacement (rayon/casier)")),
                ("est_actif", models.BooleanField(default=True, verbose_name="Lot actif")),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Lot",
                "verbose_name_plural": "Lots",
                "db_table": "catalogue_lot",
                "ordering": ["date_peremption"],
            },
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(fields=["medicament", "date_peremption"], name="cat_lot_med_exp_idx"),
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(fields=["est_actif"], name="cat_lot_actif_idx"),
        ),
        migrations.AddIndex(
            model_name="lot",
            index=models.Index(fields=["date_peremption"], name="cat_lot_exp_idx"),
        ),
    ]
