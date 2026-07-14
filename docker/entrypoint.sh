#!/bin/sh
set -eu

uv run python manage.py migrate --noinput
uv run python manage.py seed_mvp_content
uv run python manage.py seed_skill_assessment_catalog

exec uv run python manage.py runserver 0.0.0.0:8000
