# 004 — Role Discovery `GET /next-question/` (consistency with Skill Assessment)

**Label:** `ready-for-agent` · **Blocked by:** 001 (soft — inherit its permission pattern)

## Summary

The two surveys deliver "the next question" through different shapes: Skill Assessment has an explicit `POST /assessment-sessions/{id}/skill-assessment/next-question/` (`assessments/views.py:340-348`), while Role Discovery buries `current_question` inside the session state payload (`build_session_state`, `assessments/services/assessment_service.py:175`). Decision (grill session, 2026-08-14): pattern (A) — one consistent shape for both.

Selection is already a pure function (first eligible unanswered core question by `display_order`; `assessment_service.py:7-9,73-78`), so a safe GET is possible with no side effects.

## Verified evidence

- `get_current_question` is read-only (`assessment_service.py:73-78`); the old selection-event INSERT (B5.2) was removed together with the bandit — verified in the module docstring
- Skill Assessment next-question endpoint: `assessments/views.py:309-348`

## Proposed contract

`GET /api/v1/assessment-sessions/{id}/next-question/` →

- the current Role Discovery question (same serialized shape as today's `current_question`, incl. `response_scale` for `likert_5` and translations per session language)
- `null` when the role stage is exhausted / session completed
- OpenAPI schema + examples

## Acceptance criteria

- [ ] Endpoint is read-only (no DB writes on GET — assert query-write isolation in a test if feasible)
- [ ] Returns `null` (or a `next_question: null` envelope consistent with the Skill Assessment shape) when no question remains
- [ ] `current_question` stays in the session payload during a deprecation window; document removal plan in the PR
- [ ] API tests cover: in-progress session, exhausted session, completed session
- [ ] `uv run pytest -n auto` and `uv run ruff check .` pass
