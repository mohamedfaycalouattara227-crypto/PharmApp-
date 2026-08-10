from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0004_durcissement_contraintes_lots"),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE catalogue_medicament SET code_cis = NULL WHERE code_cis = '';",
            reverse_sql="UPDATE catalogue_medicament SET code_cis = '' WHERE code_cis IS NULL;",
        ),
        migrations.AlterField(
            model_name="medicament",
            name="code_cis",
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                unique=True,
                verbose_name="Code CIS (identifiant unique)",
            ),
        ),
    ]
