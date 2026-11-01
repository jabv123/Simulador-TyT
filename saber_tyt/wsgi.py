"""Configuración WSGI del proyecto."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saber_tyt.settings.development")

application = get_wsgi_application()
