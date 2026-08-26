#!/bin/sh
set -eu

# The image puts /opt/venv on PATH, so python and gunicorn resolve to the
# prepared environment — no uv at runtime.
#
# migrate and sync_content deliberately do NOT run here: every replica runs this
# script, so stacked deployments raced each other through the migration chain and
# killed sync_content mid-transaction. They live in railway.json's
# preDeployCommand instead, which Railway runs exactly once per deployment and
# which aborts the deploy on failure. collectstatic stays because it writes into
# this container's own static_root/ that whitenoise serves from.
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${WEB_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
