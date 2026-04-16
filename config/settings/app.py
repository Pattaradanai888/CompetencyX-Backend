import os

from .base import *


DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() in {'1', 'true', 'yes', 'on'}

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', SECRET_KEY)

allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(',') if host.strip()]

CORS_ALLOW_ALL_ORIGINS = os.getenv('DJANGO_CORS_ALLOW_ALL_ORIGINS', 'true').lower() in {
    '1',
    'true',
    'yes',
    'on',
}

database_name = os.getenv('DJANGO_SQLITE_NAME')
if database_name:
    DATABASES['default']['NAME'] = BASE_DIR / database_name
