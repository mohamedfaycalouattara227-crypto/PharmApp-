import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models
import django.contrib.auth.hashers


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="UtilisateurPharmacien",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="Adresse e-mail")),
                ("prenom", models.CharField(max_length=100, verbose_name="Prénom")),
                ("nom", models.CharField(max_length=100, verbose_name="Nom")),
                ("role", models.CharField(
                    choices=[
                        ("stagiaire", "Stagiaire"),
                        ("caissier", "Caissier(ère)"),
                        ("assistant", "Pharmacien(ne) assistant(e)"),
                        ("gestionnaire_stock", "Gestionnaire de stock"),
                        ("pharmacien_adjoint", "Pharmacien(ne) adjoint(e)"),
                        ("titulaire", "Pharmacien(ne) titulaire"),
                        ("administrateur", "Administrateur système"),
                    ],
                    default="caissier",
                    max_length=30,
                    verbose_name="Rôle",
                )),
                ("telephone", models.CharField(blank=True, max_length=20, verbose_name="Téléphone")),
                ("numero_ordre", models.CharField(blank=True, max_length=50, verbose_name="Numéro d'ordre (pharmaciens diplômés)")),
                ("est_actif", models.BooleanField(default=True, verbose_name="Compte actif")),
                ("est_verrouille", models.BooleanField(default=False, verbose_name="Compte verrouillé")),
                ("tentatives_connexion_echouees", models.PositiveSmallIntegerField(default=0)),
                ("verrouille_jusqu_au", models.DateTimeField(blank=True, null=True)),
                ("cree_le", models.DateTimeField(auto_now_add=True)),
                ("modifie_le", models.DateTimeField(auto_now=True)),
                ("derniere_connexion_reussie", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Utilisateur",
                "verbose_name_plural": "Utilisateurs",
                "db_table": "authentification_utilisateur",
                "ordering": ["nom", "prenom"],
            },
        ),
    ]
