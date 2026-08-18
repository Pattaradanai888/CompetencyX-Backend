# Tickets pending GitHub publication

Tickets 001–004 came out of the grill session on 2026-08-14 ("API พร้อม serve"); 005–007 out of the session on 2026-08-18, which walked the live product end to end. Once `gh` auth works, create the real issues from this folder, then delete it.

## Status

| # | Title | Status |
|---|---|---|
| 001 | Fix IDOR: bind assessment sessions to an ownership token | open |
| 002 | Expose a role's full roadmap via the API | **done** — `GET /api/v1/catalog/roles/{slug}/roadmap/` |
| 003 | Make recommendations deterministic + restore prerequisite gating | **done** — seeded per-session RNG; gating behind `_mastery_gating_enabled()`, off until 005 provides a mastery source |
| 004 | Role Discovery `GET /next-question/` | open |
| 005 | Skill Assessment asks about the role's own topics | open — see [ADR-0002](../adr/0002-skill-assessment-measures-topic-self-placement.md) |
| 006 | Derive the readiness target from the role, not from a constant | open — blocked by 005 |
| 007 | Close the Skill Assessment role guidance gap | open — blocked by 005 |

## Publish

```
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Fix IDOR: bind assessment sessions to an ownership token" --body-file 001-idor-session-ownership-token.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Role Discovery GET /next-question/ (consistency with Skill Assessment)" --body-file 004-role-discovery-next-question.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Skill Assessment asks about the role's own topics" --body-file 005-topic-anchored-skill-assessment.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Derive the readiness target from the role, not from a constant" --body-file 006-role-derived-readiness-target.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Close the Skill Assessment role guidance gap" --body-file 007-skill-assessment-role-guidance-coverage.md
```

If the `ready-for-agent` label does not exist yet: `gh label create ready-for-agent --color 0e8a16`

Suggested order: 005 first — it is the largest and unblocks 006 and 007, and until it lands the product cannot honestly claim Skill Assessment measures readiness for a role. 001 before any public exposure. 004 is small and independent.
