# Tickets pending GitHub publication

These four tickets were produced by the grill session on 2026-08-14 ("API พร้อม serve"). Once `gh` auth works, create the real issues from this folder, then delete it.

```
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Fix IDOR: bind assessment sessions to an ownership token" --body-file 001-idor-session-ownership-token.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Expose a role's full roadmap via the API" --body-file 002-role-roadmap-endpoint.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Make recommendations deterministic + restore prerequisite gating" --body-file 003-deterministic-recommendations.md
gh issue create --repo Pattaradanai888/CompetencyX-Backend --label ready-for-agent --title "Role Discovery GET /next-question/ (consistency with Skill Assessment)" --body-file 004-role-discovery-next-question.md
```

If the `ready-for-agent` label does not exist yet: `gh label create ready-for-agent --color 0e8a16`

Suggested order: 001 → 003 → 004 → 002 (blocker first, then smallest, then the read-only feature).
