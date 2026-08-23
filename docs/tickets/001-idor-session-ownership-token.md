# 001 — Fix IDOR: bind assessment sessions to an ownership token

> **Superseded by real accounts (ADR-0003).** The anonymous ownership token below was rejected: a mark that a
> cleared browser destroys is not a statement about the person. The IDOR it describes is closed instead by
> accounts plus session ownership — see GitHub issues #3 and #4. Kept for the record; do not implement.

**Label:** ~~`ready-for-agent`~~ superseded · **Blocks:** 002, 004 (soft — they should inherit the permission pattern)

## Summary

Any client holding a session UUID can read/write that session (`DEFAULT_PERMISSION_CLASSES = AllowAny`, `config/settings/base.py:105-107`; no view overrides permission). This is the only hard safety blocker for serving the API to any external consumer.

## Verified evidence

- `REST_FRAMEWORK` default permission is `AllowAny`, only `SessionAuthentication` (`config/settings/base.py:96-111`)
- `AssessmentSessionViewSet` (`assessments/views.py:58`) sets no `permission_classes` / `authentication_classes`
- `AssessmentSession.user` is nullable (`assessments/models.py:44-50`) — sessions are anonymous today

## Design decision already made (grill session, 2026-08-14)

Anonymous-first: a session can be created and used without an account. To close IDOR without forcing sign-up, the server issues an **opaque ownership token** when the session is created (store only a hash), and every session-scoped endpoint requires it. A future sign-up flow may claim a session by setting `user`.

## Acceptance criteria

- [ ] `POST /api/v1/assessment-sessions/` returns the ownership token exactly once in the create response
- [ ] All session-scoped endpoints (`retrieve`, `insights`, `results`, `history`, `answers`, `skill-assessment*`) reject requests with a missing/wrong token (403/401) and a wrong-but-valid token for another session (403)
- [ ] Token is stored hashed (not plaintext) on the session
- [ ] Existing tests updated; new API tests cover: no token → rejected, wrong token → rejected, correct token → allowed
- [ ] `uv run pytest -n auto` and `uv run ruff check .` pass

## Out of scope

API keys / partner identity / metering (per ADR-0001 and the speculative-platform decision).
