from .base import *


DEBUG = False
SECRET_KEY = 'test-secret-key'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
CORS_ALLOW_ALL_ORIGINS = True

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

DATABASES['default']['NAME'] = BASE_DIR / 'test_db.sqlite3'
