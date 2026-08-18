# Tickets pending GitHub publication

Tickets 001–004 came out of the grill session on 2026-08-14 ("API พร้อม serve"); 005–007 out of the session on 2026-08-18, which walked the live product end to end. Once `gh` auth works, create the real issues from this folder, then delete it.

## Status

| # | Title | Status |
|---|---|---|
| 001 | Fix IDOR: bind assessment sessions to an ownership token | open |
| 002 | Expose a role's full roadmap via the API | **done** — `GET /api/v1/catalog/roles/{slug}/roadmap/` |
| 003 | Make recommendations deterministic + restore prerequisite gating | **done** — seeded per-session RNG; gating behind `_mastery_gating_enabled()`, off until 005 provides a mastery source |
| 004 | Role Discovery `GET /next-question/` | open |
| 005 | Skill Assessment asks about the role's own topics | **done** — 286 topic-anchored items across 26 roles; state carries `topic_mastery` and `recommended_topics` |
| 006 | Derive the readiness target from the role, not from a constant | **done** — target rises with how many topics depend on a topic; `TARGET_READINESS_SCORE` gone |
| 007 | Close the Skill Assessment role guidance gap | **done** — all 26 roles have their own guidance, held by two tests |

## Publish

```
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Fix IDOR: bind assessment sessions to an ownership token" --body-file 001-idor-session-ownership-token.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Role Discovery GET /next-question/ (consistency with Skill Assessment)" --body-file 004-role-discovery-next-question.md
```

If the `ready-for-agent` label does not exist yet: `gh label create ready-for-agent --color 0e8a16`

Suggested order: 001 before any public exposure; 004 is small and independent.

Two things ADR-0002 called for are deliberately still open after 005:

- Prerequisite gating for curated topics stays off. Mastery now exists, but it is held against imported roadmap topics while `_mastery_gating_enabled()` governs the curated catalog; connecting them is separate work.
- The five-point agreement scale is reused rather than the three levels the ADR sketches, so the answer shape and the frontend scale are unchanged.
