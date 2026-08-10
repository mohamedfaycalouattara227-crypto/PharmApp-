import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogue", "0001_initial"),
        ("ordonnances", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistreProduitControle",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("medicament", models.ForeignKey(
                    limit_choices_to={"est_produit_controle": True},
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="registre_controle",
                    to="catalogue.medicament",
                )),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registre_controle", to="catalogue.lot")),
                ("numero_lot_fabricant", models.CharField(max_length=100)),
                ("type_mouvement", models.CharField(
                    choices=[
                        ("entree", "Entrée (réception)"),
                        ("sortie_vente", "Sortie (vente sur ordonnance)"),
                        ("retour", "Retour fournisseur"),
                        ("mise_au_rebut", "Mise au rebut (périmé)"),
                        ("controle_autorite", "Contrôle autorités (inventaire)"),
                    ],
                    max_length=25,
                )),
                ("quantite_mouvement", models.PositiveIntegerField()),
                ("unite", models.CharField(max_length=50, verbose_name="Unité (ampoules, comprimés…)")),
                ("stock_avant", models.PositiveIntegerField()),
                ("stock_apres", models.PositiveIntegerField()),
                ("ordonnance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mouvements_controles", to="ordonnances.ordonnance", verbose_name="Ordonnance sécurisée")),
                ("prescripteur_nom", models.CharField(blank=True, max_length=200)),
                ("prescripteur_num_ordre", models.CharField(blank=True, max_length=50, verbose_name="N° d'ordre du médecin")),
                ("patient_nom_chiffre", models.TextField(blank=True, default="", verbose_name="Nom patient (chiffré AES-256-GCM, base64)")),
                ("numero_registre_national", models.CharField(blank=True, max_length=50, verbose_name="N° de registre national réglementaire")),
                ("effectue_par", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mouvements_controles", to=settings.AUTH_USER_MODEL, verbose_name="Pharmacien responsable")),
                ("supervise_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supervisions_controles", to=settings.AUTH_USER_MODEL, verbose_name="Superviseur (titulaire)")),
                ("motif", models.TextField(blank=True)),
                ("notes_reglementaires", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Registre produit contrôlé",
                "verbose_name_plural": "Registre produits contrôlés",
                "db_table": "produits_controles_registre",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="registreproduitcontrole", index=models.Index(fields=["medicament", "cree_le"], name="pc_med_date_idx")),
        migrations.AddIndex(model_name="registreproduitcontrole", index=models.Index(fields=["type_mouvement", "cree_le"], name="pc_type_date_idx")),
    ]
