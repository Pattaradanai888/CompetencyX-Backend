"""Load a local ``.env`` file into ``os.environ`` for non-container runs.

``docker-compose`` already substitutes ``.env`` values, but a bare
``python manage.py runserver`` never saw them, which is why the secure
``DJANGO_DEBUG`` default had to be edited in code to develop locally.
Existing environment variables always win, so a container's real
configuration is never overridden by a developer's ``.env``.
"""

import os
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent.parent / '.env'


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, _, value = line.partition('=')
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
