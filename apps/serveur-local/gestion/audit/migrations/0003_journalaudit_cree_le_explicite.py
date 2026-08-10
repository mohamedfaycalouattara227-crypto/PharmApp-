# Généré manuellement — audit du 2026-07-21 (correctif intégrité journal).
#
# JournalAudit.cree_le n'est plus auto_now_add=True : la valeur est désormais
# fixée explicitement par JournalAuditManager.journaliser() AVANT le calcul
# de l'empreinte SHA-256, afin que verifier_integrite() reste cohérent avec
# la valeur réellement persistée. Aucun changement de colonne en base
# (toujours un DateTimeField NOT NULL) — seul le comportement applicatif
# Django change, mais Django exige que l'état de migration reflète l'option
# de champ retirée.
#
# NB : n'a pas pu être généré via `manage.py makemigrations` dans cet
# environnement (Django non installé, pas d'accès réseau) ; à valider avec
# `python manage.py makemigrations --check --dry-run` avant fusion.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_alter_journalaudit_managers_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journalaudit",
            name="cree_le",
            field=models.DateTimeField(),
        ),
    ]
