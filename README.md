# CompetencyX Backend MVP

Adaptive career-roadmap backend API built with Django and Django REST Framework.

This MVP follows the `adaptive-career-roadmap-design-draft.md` flow:
- start an assessment session
- infer or confirm a role
- ask multiple-choice skill questions
- estimate mastery
- recommend the next topic
- expose results/history through the API

## Runtime

The runnable MVP target is Docker + PostgreSQL.

### Start the stack

1. Create a local environment file:

```powershell
Copy-Item .env.example .env
```

2. Start the services:

```powershell
docker compose up --build
```

The container startup flow will:
- run database migrations
- run `seed_mvp_content`
- start Django on `http://localhost:8000`

### Main URLs

- API health: `http://localhost:8000/api/health/`
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Role catalog: `http://localhost:8000/api/catalog/roles/`

## Seeded MVP Data

The example seed set includes all draft roles:
- frontend engineer
- backend engineer
- full-stack engineer
- DevOps engineer
- data engineer
- mobile engineer
- QA / test engineer
- cybersecurity engineer

Each role has:
- 3 roadmap topics
- 2 prerequisite edges across the topic chain
- 2 skill questions
- a reachable recommendation path

## Content Sources

The project now separates content into two layers:

- Curated app-owned content:
  - `data/content/roles.yaml`
  - `data/content/topics.yaml`
  - `data/content/questions.yaml`
- Raw upstream roadmap snapshots:
  - `data/upstream/roadmap_sh/*.json`

Runtime recommendation logic uses normalized Django models, not raw upstream files.

## Reseeding

To reseed the example catalog manually:

```powershell
.venv\Scripts\python.exe manage.py seed_mvp_content
```

Inside Docker:

```powershell
docker compose exec web uv run python manage.py seed_mvp_content
```

The seed command is idempotent.

### Load curated content directly

```powershell
.venv\Scripts\python.exe manage.py load_curated_content
```

### Import a raw roadmap snapshot

```powershell
.venv\Scripts\python.exe manage.py import_roadmap_snapshot --path data/upstream/roadmap_sh/backend-engineer.sample.json --role-slug backend-engineer --source roadmap.sh --source-version sample-v1
```

## Example API Flow

### 1. Create a session with a preferred role

```http
POST /api/assessment-sessions/
Content-Type: application/json

{
  "preferred_role_slug": "backend-engineer",
  "profile": {
    "education_level": "student",
    "current_stage": "beginner"
  }
}
```

### 2. Submit answers until the recommendation is ready

Use the `current_question.id` from the session payload and submit one of that question's options:

```http
POST /api/assessment-sessions/{session_id}/answers/
Content-Type: application/json

{
  "question_id": 12,
  "option_id": 34,
  "confidence_indicator": "high"
}
```

### 3. Read the final result

- `GET /api/assessment-sessions/{session_id}/results/`
- `GET /api/assessment-sessions/{session_id}/history/`

The in-progress session payload returns lean guidance only:
- preferred role
- best-fit role
- best-fit confidence
- guidance summary
- current question

The final results payload returns:
- preferred-path recommendation
- optional best-fit-path recommendation
- preferred-role gap topics

## Local Checks

```powershell
uv run ruff check .
uv run pytest
```

## Notes

- `config.settings.runtime` is the runtime settings module.
- `config.settings.test` is the pytest settings module.
- Tests use SQLite for speed; runtime is intended for PostgreSQL.
