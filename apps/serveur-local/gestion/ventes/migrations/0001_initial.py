import uuid
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clients", "0001_initial"),
        ("catalogue", "0001_initial"),
        ("ordonnances", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Vente",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("numero", models.CharField(max_length=30, unique=True, verbose_name="Numéro de vente")),
                ("vendeur", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ventes_effectuees", to=settings.AUTH_USER_MODEL, verbose_name="Vendeur")),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ventes", to="clients.client", verbose_name="Client (optionnel)")),
                ("ordonnance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ventes", to="ordonnances.ordonnance")),
                ("statut", models.CharField(
                    choices=[("en_cours", "En cours"), ("validee", "Validée"), ("annulee", "Annulée")],
                    default="validee", max_length=20,
                )),
                ("mode_paiement", models.CharField(
                    choices=[
                        ("especes", "Espèces"), ("mobile_money", "Mobile Money (Orange/Moov)"),
                        ("assurance", "Assurance / Mutuelle"), ("credit", "Crédit client"),
                        ("cheque", "Chèque"),
                    ],
                    default="especes", max_length=20,
                )),
                ("sous_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("montant_remise", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("montant_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("montant_encaisse", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("montant_rendu", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("montant_assurance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, verbose_name="Montant pris en charge par l'assurance")),
                ("annule_le", models.DateTimeField(blank=True, null=True)),
                ("annule_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ventes_annulees", to=settings.AUTH_USER_MODEL)),
                ("motif_annulation", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Vente",
                "verbose_name_plural": "Ventes",
                "db_table": "ventes_vente",
                "ordering": ["-cree_le"],
            },
        ),
        migrations.AddIndex(model_name="vente", index=models.Index(fields=["numero"], name="vente_num_idx")),
        migrations.AddIndex(model_name="vente", index=models.Index(fields=["vendeur", "cree_le"], name="vente_vendeur_idx")),
        migrations.AddIndex(model_name="vente", index=models.Index(fields=["statut", "cree_le"], name="vente_statut_idx")),
        migrations.CreateModel(
            name="LigneVente",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("vente", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lignes", to="ventes.vente")),
                ("medicament", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lignes_vente", to="catalogue.medicament")),
                ("lot", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lignes_vente", to="catalogue.lot")),
                ("quantite", models.PositiveIntegerField()),
                ("prix_unitaire", models.DecimalField(decimal_places=2, max_digits=10)),
                ("taux_remise", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("prix_unitaire_apres_remise", models.DecimalField(decimal_places=2, max_digits=10)),
                ("montant_ligne", models.DecimalField(decimal_places=2, max_digits=12)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Ligne de vente",
                "verbose_name_plural": "Lignes de vente",
                "db_table": "ventes_ligne",
            },
        ),
        migrations.CreateModel(
            name="ClotureCaisse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date_cloture", models.DateField(unique=True, verbose_name="Date de clôture")),
                ("caissier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="clotures_effectuees", to=settings.AUTH_USER_MODEL)),
                ("validee_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="clotures_validees", to=settings.AUTH_USER_MODEL)),
                ("fond_caisse_ouverture", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("fond_caisse_cloture", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("recettes_especes", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("recettes_mobile_money", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("recettes_assurance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("recettes_credit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("recettes_cheque", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("chiffre_affaires", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("nombre_ventes", models.PositiveIntegerField(default=0)),
                ("nombre_annulations", models.PositiveIntegerField(default=0)),
                ("ecart_caisse", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10, verbose_name="Écart de caisse (FCFA)")),
                ("statut", models.CharField(
                    choices=[("en_cours", "En cours"), ("validee", "Validée"), ("litigieuse", "Litigieuse (écart détecté)")],
                    default="en_cours", max_length=15,
                )),
                ("notes", models.TextField(blank=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Clôture de caisse",
                "verbose_name_plural": "Clôtures de caisse",
                "db_table": "ventes_cloture_caisse",
                "ordering": ["-date_cloture"],
            },
        ),
    ]
