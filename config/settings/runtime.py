import os

from django.core.exceptions import ImproperlyConfigured

from .base import *


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {'1', 'true', 'yes', 'on'}


def _env_list(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(',') if item.strip()]


DATABASES = {alias: config.copy() for alias, config in DATABASES.items()}

DEBUG = _env_flag('DJANGO_DEBUG', False)
runtime_secret_key = os.getenv('DJANGO_SECRET_KEY')
if not runtime_secret_key and not DEBUG:
    msg = 'DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.'
    raise ImproperlyConfigured(msg)
SECRET_KEY = runtime_secret_key or SECRET_KEY
ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CORS_ALLOW_ALL_ORIGINS = _env_flag('DJANGO_CORS_ALLOW_ALL_ORIGINS', False)

postgres_host = os.getenv('POSTGRES_HOST')
if postgres_host:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'competencyx'),
        'USER': os.getenv('POSTGRES_USER', 'competencyx'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'competencyx'),
        'HOST': postgres_host,
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('POSTGRES_CONN_MAX_AGE', '60')),
    }
else:
    sqlite_name = os.getenv('DJANGO_SQLITE_NAME')
    if sqlite_name:
        DATABASES['default']['NAME'] = BASE_DIR / sqlite_name
