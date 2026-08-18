"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

from config.env import load_env_file


load_env_file()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.runtime')

application = get_wsgi_application()
