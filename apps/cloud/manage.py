#!/usr/bin/env python
"""manage.py — Utilitaire Django CLI pour pharmapp_cloud."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmapp_cloud.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Vérifiez que l'environnement virtuel "
            "est activé et que les dépendances sont installées."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
