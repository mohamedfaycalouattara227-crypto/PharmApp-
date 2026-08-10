"""
Migration : rapports/0002_index_rapports.py
ÉTAPE 06 — Index de performance sur RapportGenere.

Objectifs :
  - IDX (type_rapport, cree_le) : accélère les requêtes GET /api/rapports/?type=...
  - IDX (periode_debut, periode_fin) : accélère les purges et recherches par période

Aucune contrainte CHECK nécessaire (type_rapport est un CharField choices,
la DB ne peut pas valider les enums applicatifs en SQLite/PostgreSQL sans extension).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rapports", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="rapportgenere",
            index=models.Index(
                fields=["type_rapport", "cree_le"],
                name="idx_rapport_type_cree_le",
            ),
        ),
        migrations.AddIndex(
            model_name="rapportgenere",
            index=models.Index(
                fields=["periode_debut", "periode_fin"],
                name="idx_rapport_periode",
            ),
        ),
    ]
