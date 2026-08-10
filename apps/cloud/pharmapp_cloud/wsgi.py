"""
pharmapp_cloud/wsgi.py — Point d'entrée WSGI (Gunicorn en production).
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmapp_cloud.settings")
application = get_wsgi_application()
