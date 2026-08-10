import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import gestion.audit.models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="JournalAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type_action", models.CharField(
                    choices=[
                        ("connexion_reussie", "Connexion réussie"),
                        ("connexion_echouee", "Connexion échouée"),
                        ("deconnexion", "Déconnexion"),
                        ("vente_creee", "Vente créée"),
                        ("vente_annulee", "Vente annulée"),
                        ("ajustement_stock", "Ajustement de stock"),
                        ("reception_stock", "Réception fournisseur"),
                        ("alerte_stock", "Alerte stock générée"),
                        ("inventaire_demarre", "Inventaire démarré"),
                        ("inventaire_valide", "Inventaire validé"),
                        ("ordonnance_numerisee", "Ordonnance numérisée"),
                        ("acces_sensible", "Accès données sensibles"),
                        ("produit_controle_mouvement", "Mouvement produit contrôlé"),
                        ("cloture_caisse", "Clôture de caisse"),
                        ("modification_utilisateur", "Modification compte utilisateur"),
                        ("creation_compte", "Création de compte"),
                        ("suppression_compte", "Désactivation de compte"),
                        ("export_donnees", "Export de données"),
                        ("integrite_verifiee", "Vérification intégrité journal"),
                    ],
                    max_length=40,
                )),
                ("description", models.TextField()),
                ("severite", models.CharField(
                    choices=[
                        ("info", "Information"),
                        ("avertissement", "Avertissement"),
                        ("alerte", "Alerte"),
                        ("critique", "Critique"),
                    ],
                    default="info", max_length=15,
                )),
                ("utilisateur", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journal_audit", to=settings.AUTH_USER_MODEL)),
                ("adresse_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("id_objet", models.CharField(blank=True, max_length=100)),
                ("modele_source", models.CharField(blank=True, max_length=100)),
                ("donnees_supplementaires", models.JSONField(blank=True, default=dict)),
                ("empreinte_sha256", models.CharField(blank=True, max_length=64)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Entrée d'audit",
                "verbose_name_plural": "Journal d'audit",
                "db_table": "audit_journal",
                "ordering": ["-cree_le"],
            },
            managers=[("objects", gestion.audit.models.JournalAuditManager())],
        ),
        migrations.AddIndex(model_name="journalaudit", index=models.Index(fields=["type_action", "cree_le"], name="audit_type_date_idx")),
        migrations.AddIndex(model_name="journalaudit", index=models.Index(fields=["utilisateur", "cree_le"], name="audit_user_date_idx")),
        migrations.AddIndex(model_name="journalaudit", index=models.Index(fields=["severite", "cree_le"], name="audit_sev_date_idx")),
        migrations.AddIndex(model_name="journalaudit", index=models.Index(fields=["cree_le"], name="audit_date_idx")),
    ]
