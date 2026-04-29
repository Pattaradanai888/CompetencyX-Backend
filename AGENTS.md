# Repository Guidelines

## Project Structure & Module Organization
`config/` holds Django settings and root URL wiring, with runtime settings in `config/settings/runtime.py` and test settings in `config/settings/test.py`. Feature apps live in `api/`, `assessments/`, `roadmaps/`, and `recommendations/`; keep app logic close to its `models.py`, `serializers.py`, `views.py`, and `tests.py`. Seeded and upstream content lives under `data/content/` and `data/upstream/`. Docker assets are in `docker/`, and coverage output is written to `coverage/`.

## Build, Test, and Development Commands
Use `uv` for local Python workflows and Docker for the runtime stack.

- `docker compose up --build`: start PostgreSQL and the Django app, run migrations, and seed MVP content.
- `uv run pytest -n auto`: run the full test suite in parallel with coverage using `config.settings.test`.
- `uv run ruff check .`: run lint checks across the repository.
- `.venv\Scripts\python.exe manage.py seed_mvp_content`: reseed the local catalog.
- `.venv\Scripts\python.exe manage.py load_curated_content`: load YAML-curated roles, topics, and questions.

## Coding Style & Naming Conventions
Target Python 3.12 and follow Ruff defaults configured in `pyproject.toml`. Use 4-space indentation, single quotes, and keep lines within the configured 150-character limit. Prefer Django naming patterns: `PascalCase` for models/serializers, `snake_case` for functions and fields, and descriptive app-local module names. Do not edit generated migration files unless the change explicitly requires it.

## Testing Guidelines
Pytest is the test runner, with discovery enabled for `tests.py` and `test_*.py` inside `api`, `roadmaps`, `assessments`, `recommendations`, and `config`. Add tests alongside the app they cover. Favor API and service-level tests that exercise seeded flows and serializer behavior. Run tests with `-n auto` (for example, `uv run pytest -n auto`) before opening a PR; coverage XML is generated at `coverage/coverage.xml`.

## Commit & Pull Request Guidelines
Recent history uses concise, imperative commit messages with Conventional Commit prefixes such as `feat:`. Follow that style when possible, for example `fix: handle missing recommendation path`. Keep commits scoped to one change. PRs should include a short summary, linked issue or task reference, notes about migrations or seed-data changes, and example API payloads or screenshots for behavior changes affecting consumers.

## Configuration & Data Notes
Copy `.env.example` to `.env` for local runtime configuration. Runtime targets PostgreSQL in Docker, while tests use SQLite for speed. Treat files in `data/upstream/` as imported source material and keep normalized application behavior in Django models rather than raw JSON.
