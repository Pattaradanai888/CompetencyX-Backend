#!/bin/sh
set -eu

uv run python manage.py migrate --noinput
uv run python manage.py sync_content

exec uv run python manage.py runserver 0.0.0.0:8000
