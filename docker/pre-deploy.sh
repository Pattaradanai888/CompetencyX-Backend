#!/bin/sh
set -eu

# Railway runs this once per deployment, before any replica starts, and aborts the
# deploy if it exits non-zero.
#
# wait_for_db comes first because the Postgres service restarts on its own schedule:
# when it does, it replays WAL for a second or two and rejects every connection with
# "FATAL: the database system is starting up". migrate used to run straight into that
# window and fail the whole deploy.
python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-90}"
python manage.py migrate --noinput
python manage.py sync_content
