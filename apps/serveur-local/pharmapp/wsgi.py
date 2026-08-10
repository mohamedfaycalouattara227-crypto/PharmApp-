"""Point d'entrée WSGI pour PharmApp."""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmapp.settings")
application = get_wsgi_application()
