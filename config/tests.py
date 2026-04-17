import importlib
import os
from unittest.mock import patch

from django.test import SimpleTestCase


class RuntimeSettingsTests(SimpleTestCase):
    def test_runtime_settings_use_sqlite_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            module = importlib.import_module('config.settings.runtime')
            reloaded = importlib.reload(module)

        assert reloaded.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'

    def test_runtime_settings_switch_to_postgres_when_env_present(self):
        env = {
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
