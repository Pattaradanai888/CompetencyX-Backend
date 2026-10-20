import importlib
import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class RuntimeSettingsTests(SimpleTestCase):
    def test_database_url_preserves_neon_tls_options(self):
        env = {
            'DJANGO_SECRET_KEY': 'runtime-test-secret',
            'DATABASE_URL': ('postgresql://example:example@db.example.invalid/app?sslmode=require&channel_binding=require&connect_timeout=10'),
            'POSTGRES_CONN_MAX_AGE': '0',
        }
        with patch.dict(os.environ, env, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert reloaded.DATABASES['default']['OPTIONS'] == {
            'sslmode': 'require',
            'channel_binding': 'require',
            'connect_timeout': '10',
        }
        assert reloaded.DATABASES['default']['CONN_MAX_AGE'] == 0

    def test_vercel_hosts_proxy_and_explicit_cors_origins(self):
        env = {
            'DJANGO_SECRET_KEY': 'runtime-test-secret',
            'VERCEL': '1',
            'VERCEL_URL': 'api-preview.example.invalid',
            'VERCEL_PROJECT_PRODUCTION_URL': 'api.example.invalid',
            'DJANGO_CORS_ALLOWED_ORIGINS': 'https://web.example.invalid',
        }
        with patch.dict(os.environ, env, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert 'api-preview.example.invalid' in reloaded.ALLOWED_HOSTS
        assert 'api.example.invalid' in reloaded.ALLOWED_HOSTS
        assert 'https://api.example.invalid' in reloaded.CSRF_TRUSTED_ORIGINS
        assert reloaded.CORS_ALLOWED_ORIGINS == ['https://web.example.invalid']
        assert reloaded.CORS_ALLOW_ALL_ORIGINS is False
        assert reloaded.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')

    def test_runtime_settings_use_sqlite_by_default(self):
        with patch.dict(os.environ, {'DJANGO_DEBUG': 'true'}, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert reloaded.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'

    def test_runtime_settings_require_secret_key_when_debug_is_disabled(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesMessage(ImproperlyConfigured, 'DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false.'),
        ):
            module = importlib.import_module('config.settings.runtime')
            importlib.reload(module)

    def test_runtime_settings_use_secure_defaults_when_secret_key_is_present(self):
        with patch.dict(os.environ, {'DJANGO_SECRET_KEY': 'runtime-test-secret'}, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert reloaded.DEBUG is False
        assert reloaded.CORS_ALLOW_ALL_ORIGINS is False
        assert reloaded.SECRET_KEY == 'runtime-test-secret'

    def test_runtime_settings_switch_to_postgres_when_env_present(self):
        env = {
            'DJANGO_SECRET_KEY': 'runtime-test-secret',
            'POSTGRES_HOST': 'db',
            'POSTGRES_DB': 'competencyx',
            'POSTGRES_USER': 'competencyx',
            'POSTGRES_PASSWORD': 'competencyx',
            'POSTGRES_PORT': '5432',
        }
        with patch.dict(os.environ, env, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert reloaded.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'
        assert reloaded.DATABASES['default']['HOST'] == 'db'
        assert reloaded.DATABASES['default']['NAME'] == 'competencyx'
