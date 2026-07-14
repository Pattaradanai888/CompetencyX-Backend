# CompetencyX Frontend Integration Notes

## Overview
This document summarizes the current assessment API contract after the role-discovery refactor.

- Backend base URL for local development: `http://localhost:8000`
- Live schema endpoint: `GET /api/schema/`
- Swagger UI: `GET /api/schema/swagger-ui/`
- Checked-in schema snapshot: [docs/openapi.json](/D:/Flook/SE/Personal%20Project/CompentencyX/docs/openapi.json)
- Authentication: none currently required

The backend remains the source of truth for:

- question selection
- role-discovery progression
- role resolution state
- Skill Assessment (PSP/SDLC self-rating) state
- final recommendation output

## Main Contract Changes
### Lean session payloads
`POST /api/v1/assessment-sessions/`, `GET /api/v1/assessment-sessions/{id}/`, and `POST /api/v1/assessment-sessions/{id}/answers/` now return a lean session-state payload.

Fields included:

- `id`
- `status`
- `phase`
- `language`
- `best_fit_confidence`
- `preferred_role`
- `best_fit_role`
- `profile`
- `started_at`
- `updated_at`
- `completed_at`
- `milestones`
- `role_alignment_status`
- `role_resolution_status`
- `guidance_summary`
- `current_question`

Fields removed from the in-progress session payload:

- `top_role_candidates`
- `mastery_scores`
- recommendation objects
- detailed pillar analysis

### Public question shape
`current_question` still contains:

- `id`
- `code`
- `stage`
- `question_type`
- `prompt`
- `help_text`
- `role`
- `topic`
- `difficulty`
- `options`
- `response_scale`

`discrimination_score` is no longer exposed in the public question payload.

### Question language
Create-session accepts an optional `language` field:

```json
{
  "preferred_role_slug": "backend-developer",
  "language": "th"
}
```

Supported values are `en` and `th`. If omitted, the backend stores `language: "en"` on the session.

For `role_discovery` questions, `current_question.prompt`, `current_question.help_text`, and `response_scale[].label` are returned in the session language when a translation exists. Missing Thai translations fall back to English. Roadmap content, recommendations, and history text remain English in this pass.

Role-discovery questions use `question_type: "likert_5"` and return no `options`. Render the five radio choices from `response_scale` and submit the selected numeric `value`.

Role answer request:

```json
{
  "question_id": 101,
  "scale_value": 2,
  "response_time_ms": 4200,
  "confidence_indicator": "high"
}
```

### New insights endpoint
`GET /api/v1/assessment-sessions/{id}/insights/` was added for explainability-oriented UI or analytics views.

Response fields:

- `role_resolution_status`
- `best_fit_role`
- `best_fit_confidence`
- `answered_role_questions`
- `pillar_profile`
- `ranked_roles`
- `guidance_summary`

`pillar_profile` items contain:

- `key`
- `label`
- `raw_score`
- `normalized_score`
- `evidence_count`

`ranked_roles` items contain:

- `slug`
- `name`
- `fit_score`
- `fit_share`
- `top_supporting_pillars`

### Final results payload
`GET /api/v1/assessment-sessions/{id}/results/` still returns mastery and recommendation data, and now also includes:

- `pillar_profile`
- `ranked_roles`
- `role_resolution_status`

This means detailed role-fit analysis is available from:

- `/api/v1/assessment-sessions/{id}/insights/`
- `/api/v1/assessment-sessions/{id}/results/`

## Current Assessment Endpoints
| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/assessment-sessions/` | Creates a session and returns lean session state |
| `GET` | `/api/v1/assessment-sessions/{id}/` | Returns lean session state for recovery or refresh |
| `POST` | `/api/v1/assessment-sessions/{id}/answers/` | Submits the current answer and returns the updated lean session state |
| `GET` | `/api/v1/assessment-sessions/{id}/insights/` | Returns pillar profile and ranked-role analysis |
| `GET` | `/api/v1/assessment-sessions/{id}/results/` | Returns final recommendations, mastery, and analysis after completion |
| `GET` | `/api/v1/assessment-sessions/{id}/history/` | Returns answer and recommendation history after completion |
| `GET` | `/api/v1/assessment-sessions/{id}/skill-assessment/` | Returns saved skill assessment state (`completed`, `answers`, `completed_at`) |
| `POST` | `/api/v1/assessment-sessions/{id}/skill-assessment/` | Replaces the whole skill assessment answer set and completion state |
| `GET` | `/api/v1/assessment-sessions/{id}/skill-assessment/catalog/` | Returns the PSP/SDLC question catalog with role-aware guidance |
| `POST` | `/api/v1/assessment-sessions/{id}/skill-assessment/next-question/` | Returns the adaptively selected next skill assessment question |

Skill Assessment state is stored in dedicated tables; the session `profile` field is free-form client data only and no longer carries a `skill_assessment` key.

## Role Discovery Notes
Role discovery uses a static 46-question core SWEBOK 2024 knowledge-area profile. The backend measures work preferences across the SWEBOK knowledge areas first, then maps the completed profile to a best-fit role. If the completed profile is still low-margin, the backend may ask additional role tie-break questions before completing the session.

Each role-discovery prompt is a single statement answered with:

- `2`: Strongly agree
- `1`: Agree
- `0`: Neutral
- `-1`: Disagree
- `-2`: Strongly disagree

Relevant session fields:

- `phase`: `role_discovery` or `recommendation_ready`
- `role_resolution_status`: `in_progress`, `unknown`, `resolved`, or `low_confidence`
- `role_alignment_status`: `unknown`, `aligned`, or `mismatch`

Important implications:

- `best_fit_role` remains `null` while the 46 core role questions are still in progress
- `best_fit_confidence` remains `0.0` while the 46 core role questions are still in progress
- `role_alignment_status` remains `unknown` while the 46 core role questions are still in progress
- the insights endpoint returns an empty `ranked_roles` list until the 46 core role questions are complete
- after the 46th core role answer, the backend either resolves to one best-fit role or asks targeted tie-break questions
- once role discovery completes the session enters `recommendation_ready`; Skill Assessment is available at any time via its own endpoints

### SWEBOK role metadata
Catalog role objects now include:

- `top_ka_codes`: the role's top SWEBOK KA codes, for example `["KA4", "KA2", "KA6"]`
- `core_tasks`: role task summaries with supporting `ka_codes`
- `swebok_source_version`: currently `SWEBOK V4.0`

## OpenAPI Spec
The checked-in OpenAPI snapshot should be used as the frontend reference artifact for:

- generated types
- generated clients
- contract review

Source of truth:

- live endpoint: `GET /api/schema/`
- checked-in snapshot: [docs/openapi.json](/D:/Flook/SE/Personal%20Project/CompentencyX/docs/openapi.json)

Schema refresh command:

```bash
uv run python manage.py spectacular --format openapi-json --file docs/openapi.json
```

If frontend code relies on generated types or generated clients, regenerate them after backend serializer, schema, or route changes.
