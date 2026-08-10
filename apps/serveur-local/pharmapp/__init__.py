"""
Package principal de PharmApp — Système de gestion de pharmacie local-first.
Bobo-Dioulasso, Burkina Faso.

Ce fichier importe l'application Celery afin que les décorateurs @shared_task
soient toujours disponibles au démarrage Django.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
