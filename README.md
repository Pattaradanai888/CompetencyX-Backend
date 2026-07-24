# CompetencyX Backend

Simple Django + Django REST Framework API for adaptive career assessments and roadmap recommendations.

## Run Locally

1. Install dependencies:

```powershell
uv sync
```

2. Create your local environment file:

```powershell
Copy-Item .env.example .env
```

The example contains development-only values. Customize `.env` before using it outside local development.

3. Run locally with SQLite:

```powershell
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py sync_content
uv run --env-file .env python manage.py runserver
```

This uses the checked-in `db.sqlite3` setup.

`Skill Assessment` catalog data now lives in SQLite tables, not in hardcoded runtime Python lists. The migration seeds the default rows, and `uv run --env-file .env python manage.py sync_content` can be used any time to refresh them.

## URLs

- Health check: `http://localhost:8000/api/v1/health/`
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Role catalog: `http://localhost:8000/api/v1/catalog/roles/`

## Common Commands

```powershell
uv run pytest -n auto
uv run ruff check .
uv run --env-file .env python manage.py sync_content
uv run --env-file .env python manage.py validate_question_catalog

# Benchmarking & Simulation
uv run --env-file .env python manage.py simulate_inmemory --samples 1000
uv run --env-file .env python manage.py tune_scoring --grid data/scoring_tuning_grid.yaml --samples 500
uv run --env-file .env python manage.py simulate_personas --check-baseline data/simulation/persona_baseline.json
```

## Project Layout

- `api/` - API entry points and seeded-flow tests
- `assessments/` - assessment sessions, answers, scoring, and serializers
- `roadmaps/` - roles, topics, questions, seeds, and questionnaire logic
- `recommendations/` - recommendation behavior
- `config/` - Django settings and root URLs
- `data/content/` - curated roles, topics, and questions
- `data/upstream/` - imported source snapshots
- `simulation/` - in-memory Monte Carlo and persona-fidelity simulation engine
- `assessments/management/commands/` - simulation, scoring-tuning, and content-management commands

