# 002 — Expose a role's full roadmap via the API

**Label:** `ready-for-agent` · **Blocked by:** 001 (soft — inherit its permission pattern)

## Summary

Clients can see the role catalog (`GET /api/v1/catalog/roles/`, `roadmaps/views.py`) but **cannot browse a role's Roadmap** (topics + prerequisite ordering) through the API, even though the model exists (`RoadmapTopic`, `TopicPrerequisite` — `roadmaps/models.py:22-85`). This is the one concrete capability the product owner said is missing ("ดู roadmap ทั้ง role").

## Verified evidence

- Only `RoleViewSet` is registered under `catalog/` (`roadmaps/urls.py:7`)
- `RoadmapTopic` / `TopicPrerequisite` are seeded and used by recommendations (`recommendation_service.py:104-108`) but have no read endpoint
- Glossary terms Roadmap / Roadmap Topic / Recommendation live in `CONTEXT.md`

## Proposed contract

`GET /api/v1/catalog/roles/{slug}/roadmap/` →

- role summary (slug, name)
- ordered topics: id/slug, title, description, difficulty, topic_group, display_order, is_active filter (default only active)
- prerequisite edges: `{ topic, prerequisite, required_mastery_threshold }`
- OpenAPI schema + examples consistent with existing spectacular setup

## Acceptance criteria

- [ ] Endpoint returns active topics ordered by `display_order` with prerequisite edges
- [ ] Unknown slug → 404; documented in OpenAPI
- [ ] API tests against seeded content
- [ ] `uv run pytest -n auto` and `uv run ruff check .` pass

## Known related bug (do NOT silently fix here)

`_get_eligible_recommendation_topics` (`recommendation_service.py:102-108`) only admits topics whose prerequisites all have `required_mastery_threshold <= 0.0` — after the skill-stage removal there is no mastery source, so gated topics are never recommendable. That is ticket-003-adjacent engine work, out of scope for this read-only endpoint. (If 003 lands first, recommendation reasons may change; this endpoint is unaffected.)
