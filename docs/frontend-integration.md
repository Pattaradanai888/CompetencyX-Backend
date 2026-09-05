# CompetencyX Frontend Integration Notes

## Overview
This document summarizes the current assessment API contract after the role-discovery refactor.

- Backend base URL for local development: `http://localhost:8000`
- Live schema endpoint: `GET /api/schema/`
- Swagger UI: `GET /api/schema/swagger-ui/`
- Checked-in schema snapshot: [docs/openapi.json](/D:/Flook/SE/Personal%20Project/CompentencyX/docs/openapi.json)
- Authentication: optional token (`Authorization: Token <key>`); required only to mark a Held Topic and to list your own sessions

The backend remains the source of truth for:

- question selection
- role-discovery progression
- role resolution state
- Skill Assessment state, the stop rule (Recommendation Stability) and the suggestion order
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

### Next question, and the `current_question` deprecation window
Role Discovery now serves its next question the way Skill Assessment does, through its own read-only endpoint:

```
GET /api/v1/assessment-sessions/{id}/next-question/
-> {"next_question": { ...same shape as current_question... }}
```

`next_question` is `null` once the role stage is exhausted or the session is completed -- in this backend those are the
same moment, since running out of role questions is what completes a session. The endpoint answers only "what am I
being asked next?"; read `phase` and `status` from the session payload to tell *why* nothing is being asked. The GET
writes nothing, so it is safe to poll, retry, or replay on a page refresh.

The envelope is `{"next_question": ...}` alone. Skill Assessment adds a `progress` object to its envelope because it
has a stop rule to report against; Role Discovery has no equivalent, and its progress is already in the session
payload as `milestones`, so it is deliberately not duplicated here.

`current_question` stays in the session payload for now, carrying exactly the same value, so no client has to move in
the same release. Plan: it is deprecated from this release, clients migrate to `GET /next-question/`, and the field is
removed from the session payload once the frontend no longer reads it -- not before.

### Question language
Create-session accepts an optional `language` field:

```json
{
  "preferred_role_slug": "backend-developer",
  "language": "th"
}
```

Supported values are `en` and `th`. If omitted, the backend stores `language: "en"` on the session.

For `role_discovery` questions, `current_question.prompt`, `current_question.help_text`, and `response_scale[].label` are returned in the session language when a translation exists. Missing Thai translations fall back to English. `guidance_summary` is written in the session language. Role objects carry `name_th` / `description_th`, pillar entries `label_th`, and ranked roles `name_th` / `top_supporting_pillars_th`; a `_th` field falls back to the English value rather than to empty. Answer history text stays English.

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
- `label_th`
- `raw_score`
- `normalized_score`
- `evidence_count`

`ranked_roles` items contain:

- `slug`
- `name`
- `name_th`
- `fit_score`
- `fit_share`
- `top_supporting_pillars`
- `top_supporting_pillars_th`

### Final results payload
`GET /api/v1/assessment-sessions/{id}/results/` returns the role analysis:

- `pillar_profile`
- `ranked_roles`
- `role_resolution_status`

Nothing in it names topics to learn. `preferred_role_gap_topics` and the "Focus next on …" sentence, which listed the first
three curated topics regardless of the answers, were removed (ADR-0005): what to learn next is the Skill Assessment's
answer-derived suggestion, read from `GET …/skill-assessment/`.

This means detailed role-fit analysis is available from:

- `/api/v1/assessment-sessions/{id}/insights/`
- `/api/v1/assessment-sessions/{id}/results/`

## Accounts
A respondent registers with an email and a password, and holds the returned credential across requests as
`Authorization: Token <key>`. The email is the identifier; it is stored lower-cased, and a duplicate one is
refused with `{"email": ["An account with this email already exists."]}`. A wrong password and an unknown email
are refused identically, so the response does not disclose which accounts exist, as
`400 {"detail": ["Email or password is incorrect."]}`.

A respondent holds one credential at a time: signing in again returns the same token, and signing out revokes it
everywhere, so a second device signs the first one out. Per-device credentials would need a token per session and
are not built.

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/accounts/register/` | Creates an account; returns `{token, user}` with `201` |
| `POST` | `/api/v1/accounts/sign-in/` | Returns `{token, user}` |
| `POST` | `/api/v1/accounts/sign-out/` | Deletes the credential; returns `204`, after which the token no longer authenticates |
| `GET` | `/api/v1/accounts/me/` | Returns `{id, email}` for the signed-in respondent, `401` when signed out |

The account `id` is a UUID, so it discloses neither how many accounts exist nor the order they were created in.

### Session ownership
A session created while signed in belongs to that account, and every session-scoped endpoint below answers `404`
for anyone else — a second account or an unauthenticated caller holding the identifier. Sessions created signed
out have no owner: they stay readable, and reading one never assigns it to the account that asked.

## Current Assessment Endpoints
| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/assessment-sessions/` | Creates a session and returns lean session state; owned by the signed-in respondent, if any |
| `GET` | `/api/v1/assessment-sessions/` | Lists the sessions the signed-in respondent owns; `401` when signed out |
| `GET` | `/api/v1/assessment-sessions/{id}/` | Returns lean session state for recovery or refresh |
| `POST` | `/api/v1/assessment-sessions/{id}/answers/` | Submits the current answer and returns the updated lean session state |
| `GET` | `/api/v1/assessment-sessions/{id}/next-question/` | Returns the role discovery question the session is waiting on, or `null` |
| `GET` | `/api/v1/assessment-sessions/{id}/insights/` | Returns pillar profile and ranked-role analysis |
| `GET` | `/api/v1/assessment-sessions/{id}/results/` | Returns the role analysis after completion |
| `GET` | `/api/v1/assessment-sessions/{id}/history/` | Returns answer history after completion |
| `GET` | `/api/v1/assessment-sessions/{id}/skill-assessment/` | Returns saved skill assessment state, every unit's state, the suggestions, readiness and `progress` |
| `POST` | `/api/v1/assessment-sessions/{id}/skill-assessment/` | Replaces the whole answer set; `completed: true` is accepted only when the stop rule allows it |
| `GET` | `/api/v1/assessment-sessions/{id}/skill-assessment/catalog/` | Returns the target role's items and radar axes, one per Assessable Topic Set, plus role guidance |
| `POST` | `/api/v1/assessment-sessions/{id}/skill-assessment/next-question/` | Decides the next item and the stop rule from the answers posted, saved or not |
| `POST` | `/api/v1/assessment-sessions/{id}/skill-assessment/held-topics/` | Marks an Assessable Topic Set as already held (account required); returns the updated state |
| `DELETE` | `/api/v1/assessment-sessions/{id}/skill-assessment/held-topics/{topic_key}/` | Withdraws a mark (account required); returns the updated state |

Skill Assessment state is stored in dedicated tables; the session `profile` field is free-form client data only and no longer carries a `skill_assessment` key.

### The stop rule, and how a client should drive it (ADR-0005)
The catalog holds only the target role's Assessable Topic Sets (there is no role-independent fallback; a session with no
role gets an empty catalog). The client asks `POST …/skill-assessment/next-question/` with **all the answers it holds**,
saved or not, after every answer. The response carries the item to ask next and a `progress` object:

| Field | Meaning |
| --- | --- |
| `answered` / `total` / `remaining` | Counts over the role's sets |
| `floor` / `ceiling` | The assessment never ends before `floor` answers (12, or the catalog size) and never asks past `ceiling` (20, or the catalog size) |
| `settled` | Recommendation Stability: no single unanswered set, at any rating, could change the next five topics -- and the floor was reached |

`next_question` is `null` when the assessment should stop: `settled`, or `answered >= ceiling`, or nothing left to
ask. That is the client's signal to `POST …/skill-assessment/` with `completed: true` and the same answers; the save
applies the same rule, so it never disagrees with the last `next-question` verdict. It refuses (`400`, key `completed`)
only when the client asks to complete answers the rule does not allow, and rolls that request's answers back.

Nothing about stability is stored: the state endpoint recomputes `progress` from the saved answers on every read. On a
completed assessment `confidence` is `high` when the saved answers are settled and `low` when the ceiling ended it.

The client must not pick an item of its own when the backend cannot be reached; an order that does not come from the
backend's evidence is a guess.

### Removed: persisted path recommendations (ADR-0003)
`preferred_path_recommendation` and `best_fit_path_recommendation` are gone from the results payload, and
`recommendations` is gone from the history payload. They were produced by a Q-learning policy whose reward was a
function of the chosen topic alone, so it reproduced a sort by `display_order` at the cost of a database write per
answer. The answer-derived ordering lives in `GET /api/v1/assessment-sessions/{id}/skill-assessment/` as
`topic_mastery` and `recommended_topics`; consume those instead.

### Topic states and suggestions
`GET /api/v1/assessment-sessions/{id}/skill-assessment/` reports every Assessable Topic Set of the session's role in
`topic_states`, and the suggestions derived from the same answers in `recommended_topics` (`next_topics` is its
head). Each entry carries both the English wording and the set's Canonical Thai Wording, so a Thai session renders
Thai without rebuilding a sentence on the client; the prerequisite names a reason points at are resolved server-side.

| Field | On | Notes |
| --- | --- | --- |
| `topic_title` / `topic_title_th` | every entry | The set's wording in each language. A set whose Thai wording is still empty carries `null` in every `_th` field (and no `translations.th` in the catalog), so the page falls back deliberately rather than reading English as Thai |
| `node_slugs` | every entry | The imported roadmap node slugs the set covers, in authored order. A roadmap view marks a held set's nodes, or a suggested set's nodes, by slug rather than by matching titles |
| `state` | every entry | `held`, `assessed_gap`, or `unassessed` |
| `mastery` | every entry | Self-placed Mastery `0.0`–`1.0`; `null` when the set was never rated, including a set held by a mark alone |
| `statement` / `statement_th` | `held` entries | The respondent's own statement ("You said you can already work on …"), never a verdict |
| `held_by_mark` | `held` entries | `true` when the mark is what holds the set, so the undo control is shown; `false` when a top self-rating holds it (marked or not), because taking the mark back would change nothing |
| `reason` / `reason_th` | suggestions | Why the set is suggested, naming up to two outstanding prerequisites |

The catalog's dimension entries carry the same Thai wording under `translations.th.label` and
`translations.th.low_score_action`, so the radar axes read in the session's language too. Dimensions carry no
`track`: an axis is an Assessable Topic Set and nothing else. Catalog questions carry `topic_slug` / `topic_title`,
the set they are about.

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
