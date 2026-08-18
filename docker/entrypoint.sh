#!/bin/sh
set -eu

# The image puts /opt/venv on PATH, so python and gunicorn resolve to the
# prepared environment — no uv at runtime.
python manage.py migrate --noinput
python manage.py sync_content
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${WEB_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
