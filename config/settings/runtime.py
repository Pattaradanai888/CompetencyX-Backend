import os
from urllib.parse import unquote, urlparse

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


def _database_from_url(url: str) -> dict:
    """Translate a ``postgres://`` connection URL (Railway, Heroku, Fly) into Django's DATABASES entry."""
    parsed = urlparse(url)
    if parsed.scheme not in {'postgres', 'postgresql', 'psql'}:
        msg = f'Unsupported DATABASE_URL scheme: {parsed.scheme!r}. Only PostgreSQL URLs are supported.'
        raise ImproperlyConfigured(msg)
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parsed.path.lstrip('/')) or 'competencyx',
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': unquote(parsed.hostname or ''),
        'PORT': str(parsed.port or 5432),
        'CONN_MAX_AGE': int(os.getenv('POSTGRES_CONN_MAX_AGE', '60')),
    }


DATABASES = {alias: config.copy() for alias, config in DATABASES.items()}

DEBUG = _env_flag('DJANGO_DEBUG', False)
runtime_secret_key = os.getenv('DJANGO_SECRET_KEY')
if not runtime_secret_key and not DEBUG:
    msg = 'DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.'
    raise ImproperlyConfigured(msg)
SECRET_KEY = runtime_secret_key or SECRET_KEY
ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CORS_ALLOW_ALL_ORIGINS = _env_flag('DJANGO_CORS_ALLOW_ALL_ORIGINS', False)
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in _env_list('DJANGO_CSRF_TRUSTED_HOSTS', '') if host]

# Railway (and any PaaS behind a TLS-terminating proxy) publishes the service domain at runtime,
# so the host is not known when the image is built.
platform_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if platform_domain:
    if platform_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(platform_domain)
    platform_origin = f'https://{platform_domain}'
    if platform_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(platform_origin)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    STORAGES = {
        **STORAGES,
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
    }

database_url = os.getenv('DATABASE_URL')
postgres_host = os.getenv('POSTGRES_HOST')
if database_url:
    DATABASES['default'] = _database_from_url(database_url)
elif postgres_host:
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
