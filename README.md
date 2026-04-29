# CompetencyX Backend

Simple Django + Django REST Framework API for adaptive career assessments and roadmap recommendations.

## Run Locally

1. Install dependencies:

```powershell
uv sync
```

2. Create your local env file:

```powershell
Copy-Item .env.example .env
```

3. Run locally with SQLite:

```powershell
python manage.py migrate
python manage.py runserver
```

This uses the checked-in `db.sqlite3` setup.

## URLs

- Health check: `http://localhost:8000/api/health/`
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Role catalog: `http://localhost:8000/api/catalog/roles/`

## Common Commands

```powershell
uv run pytest -n auto
uv run ruff check .
python manage.py seed_mvp_content
python manage.py load_curated_content
uv run python manage.py validate_question_catalog
```

## Project Layout

- `api/` - API entry points and seeded-flow tests
- `assessments/` - assessment sessions, answers, scoring, and serializers
- `roadmaps/` - roles, topics, questions, seeds, and questionnaire logic
- `recommendations/` - recommendation behavior
- `config/` - Django settings and root URLs
- `data/content/` - curated roles, topics, and questions
- `data/upstream/` - imported source snapshots
