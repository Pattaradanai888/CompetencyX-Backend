# Tickets pending GitHub publication

Tickets 001–004 came out of the grill session on 2026-08-14 ("API พร้อม serve"); 005–007 out of the session on 2026-08-18, which walked the live product end to end. Every ticket here is now either built or superseded, so none of them is waiting on a GitHub issue.

## Status

| # | Title | Status |
|---|---|---|
| 001 | Fix IDOR: bind assessment sessions to an ownership token | **superseded** — the anonymous token was rejected; accounts plus session ownership close the IDOR (ADR-0003) |
| 002 | Expose a role's full roadmap via the API | **done** — `GET /api/v1/catalog/roles/{slug}/roadmap/` |
| 003 | Make recommendations deterministic + restore prerequisite gating | **done** — seeded per-session RNG; gating behind `_mastery_gating_enabled()`, off until 005 provides a mastery source |
| 004 | Role Discovery `GET /next-question/` | **done** — `GET /api/v1/assessment-sessions/{id}/next-question/`; `current_question` deprecated, still served |
| 005 | Skill Assessment asks about the role's own topics | **done** — 286 topic-anchored items across 26 roles; state carries `topic_mastery` and `recommended_topics` |
| 006 | Derive the readiness target from the role, not from a constant | **done** — target rises with how many topics depend on a topic; `TARGET_READINESS_SCORE` gone |
| 007 | Close the Skill Assessment role guidance gap | **done** — all 26 roles have their own guidance, held by two tests |

## Publish

Nothing here is left to publish: 001 was superseded by accounts (ADR-0003) and 004 is now built. Delete this folder
once its record is no longer wanted.

Two things ADR-0002 called for are deliberately still open after 005:

- Prerequisite gating for curated topics stays off. Mastery now exists, but it is held against imported roadmap topics while `_mastery_gating_enabled()` governs the curated catalog; connecting them is separate work.
- The five-point agreement scale is reused rather than the three levels the ADR sketches, so the answer shape and the frontend scale are unchanged.
