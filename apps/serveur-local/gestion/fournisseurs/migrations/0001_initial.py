"""Migration initiale du module Fournisseurs / Achats."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalogue", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Fournisseur",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=20, unique=True, verbose_name="Code fournisseur")),
                ("nom", models.CharField(max_length=200)),
                ("contact_principal", models.CharField(blank=True, max_length=200)),
                ("telephone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("adresse", models.TextField(blank=True)),
                ("ville", models.CharField(blank=True, max_length=100)),
                ("pays", models.CharField(default="Burkina Faso", max_length=100)),
                ("numero_agrement", models.CharField(blank=True, max_length=60, verbose_name="N° d'agrément pharmaceutique")),
                ("delai_livraison_jours", models.PositiveIntegerField(default=7, verbose_name="Délai de livraison indicatif (jours)")),
                ("conditions_paiement", models.CharField(blank=True, max_length=200)),
                ("actif", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Fournisseur",
                "verbose_name_plural": "Fournisseurs",
                "db_table": "fournisseurs_fournisseur",
                "ordering": ["nom"],
            },
        ),
        migrations.AddIndex(
            model_name="fournisseur",
            index=models.Index(fields=["code"], name="fourn_code_idx"),
        ),
        migrations.AddIndex(
            model_name="fournisseur",
            index=models.Index(fields=["actif", "nom"], name="fourn_actif_nom_idx"),
        ),
        migrations.CreateModel(
            name="BonCommande",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("numero", models.CharField(max_length=30, unique=True, verbose_name="Numéro de bon de commande")),
                ("statut", models.CharField(
                    choices=[
                        ("brouillon", "Brouillon"), ("envoye", "Envoyé au fournisseur"),
                        ("partiel", "Reçu partiellement"), ("recu", "Reçu intégralement"),
                        ("cloture", "Clôturé"), ("annule", "Annulé"),
                    ], default="brouillon", max_length=15)),
                ("date_commande", models.DateField()),
                ("date_livraison_prevue", models.DateField(blank=True, null=True)),
                ("total_ht", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_tva", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total_ttc", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("envoye_le", models.DateTimeField(blank=True, null=True)),
                ("cloture_le", models.DateTimeField(blank=True, null=True)),
                ("annule_le", models.DateTimeField(blank=True, null=True)),
                ("motif_annulation", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
                ("fournisseur", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="bons_commande", to="fournisseurs.fournisseur")),
                ("cree_par", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="bons_commande_crees", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Bon de commande",
                "verbose_name_plural": "Bons de commande",
                "db_table": "fournisseurs_bon_commande",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(
            model_name="boncommande",
            index=models.Index(fields=["numero"], name="bc_numero_idx"),
        ),
        migrations.AddIndex(
            model_name="boncommande",
            index=models.Index(fields=["fournisseur", "statut"], name="bc_fourn_statut_idx"),
        ),
        migrations.AddIndex(
            model_name="boncommande",
            index=models.Index(fields=["statut", "-cree_le"], name="bc_statut_date_idx"),
        ),
        migrations.CreateModel(
            name="LigneBonCommande",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantite_commandee", models.PositiveIntegerField()),
                ("quantite_recue", models.PositiveIntegerField(default=0)),
                ("prix_unitaire_ht", models.DecimalField(decimal_places=2, max_digits=10)),
                ("taux_tva", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("bon_commande", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="lignes", to="fournisseurs.boncommande")),
                ("medicament", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="lignes_bon_commande", to="catalogue.medicament")),
            ],
            options={
                "verbose_name": "Ligne de bon de commande",
                "verbose_name_plural": "Lignes de bon de commande",
                "db_table": "fournisseurs_bon_commande_ligne",
                "ordering": ["bon_commande", "medicament__nom"],
            },
        ),
        migrations.AddConstraint(
            model_name="ligneboncommande",
            constraint=models.CheckConstraint(
                check=models.Q(quantite_recue__lte=models.F("quantite_commandee")),
                name="ligne_bc_recue_lte_commandee",
            ),
        ),
        migrations.CreateModel(
            name="ReceptionBonCommande",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("numero_bordereau", models.CharField(blank=True, max_length=60)),
                ("date_reception", models.DateTimeField()),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("bon_commande", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="receptions", to="fournisseurs.boncommande")),
                ("recu_par", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="receptions_effectuees", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Réception de commande",
                "verbose_name_plural": "Réceptions de commande",
                "db_table": "fournisseurs_reception",
                "ordering": ["-date_reception"],
            },
        ),
        migrations.AddIndex(
            model_name="receptionboncommande",
            index=models.Index(fields=["bon_commande", "-date_reception"], name="reception_bc_date_idx"),
        ),
        migrations.CreateModel(
            name="LigneReception",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantite_recue", models.PositiveIntegerField()),
                ("numero_lot", models.CharField(max_length=60)),
                ("date_peremption", models.DateField()),
                ("prix_achat_unitaire", models.DecimalField(decimal_places=2, max_digits=10)),
                ("ligne_bon_commande", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="receptions", to="fournisseurs.ligneboncommande")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="receptions", to="catalogue.lot")),
                ("reception", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="lignes", to="fournisseurs.receptionboncommande")),
            ],
            options={
                "verbose_name": "Ligne de réception",
                "verbose_name_plural": "Lignes de réception",
                "db_table": "fournisseurs_reception_ligne",
            },
        ),
    ]
