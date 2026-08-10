"""
Migration 0002 : ajout du champ nb_impressions sur le modèle Vente.

Ce champ entier positif (défaut 0) est incrémenté côté serveur à chaque
appel GET /ventes/{id}/recu/. Il permet de marquer DUPLICATA dès la
deuxième impression sans dépendre du frontend.

Dépend de : 0001_initial
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vente",
            name="nb_impressions",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "Compteur incrémenté par le backend à chaque génération du DTO reçu. "
                    "reimprime = (nb_impressions > 1) dans la réponse de l'API."
                ),
                verbose_name="Nombre d'impressions du reçu",
            ),
        ),
    ]
