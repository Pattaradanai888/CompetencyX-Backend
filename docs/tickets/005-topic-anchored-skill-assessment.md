# 005 — Skill Assessment asks about the role's own topics

**Label:** `ready-for-agent` · **Blocks:** 006, 007 · **Decided by:** [ADR-0002](../adr/0002-skill-assessment-measures-topic-self-placement.md)

## Summary

Skill Assessment asks 11 general PSP/SDLC process questions that are identical for every role, and the learning sequence it produces is the role's entire roadmap in topological order, unchanged by the answers. Replace the instrument with per-topic self-placement against the role's own roadmap, and let mastery drive the recommendation again.

## Verified evidence

- `SkillAssessmentQuestion` has no `role` field (`assessments/models.py:144-152`); the same 11 items are served to every role
- Role reaches the assessment only through the Q-learning state key (`skill_assessment_service.py:92-104`), which reorders questions that are all asked anyway — verified by walking both flows: 11 answers, then completion
- 6 of 8 dimensions have exactly one question (`assessments/skill_assessment_seed_data.py:100-222`)
- The numbered learning sequence renders `displayTopics` (`app/pages/roadmaps/[sessionId].vue:978-979`), not the skill-assessment-ordered list; only `priorityTopics.slice(0, 3)` uses it (`RoadmapCompletedOverview.vue:210`)
- That ordering is substring keyword matching (`[sessionId].vue:397-436`). Measured against the imported roadmaps: 5 of 8 dimensions match zero Backend Developer topics, 6 of 8 match zero Frontend Developer topics; `sdlc-deployment` matches UX Designer's "Deploy Social Proof"
- The mastery pipeline this replaces still has its sockets: `TopicPrerequisite.required_mastery_threshold` (`roadmaps/models.py`), `RECOMMENDATION_MASTERY_THRESHOLD = 0.7` and `_mastery_gating_enabled() -> False` (`assessments/services/recommendation_service.py`)
- Prior art for the item shapes: `data/content/questions/skill/*.yaml` (26 files, `topic_signals` with `mastery_delta` 1.0 / 0.5 / 0.0). Dead today — `_load_question_bank` globs only `questions/role/*.yaml` (`roadmaps/seeds.py:58-71`) and `Question.Stage` has no `skill` member

## Design decisions already made (ADR-0002)

- Self-report, **not** a graded test. `CONTEXT.md`'s definition is unchanged and governs the wording.
- Items are drawn from the **top-level topics** of the role's imported roadmap (`ExternalRoadmapNode` where `node_type = 'topic'`), in prerequisite order.
- Three levels per item, mapping to mastery — never encountered / can explain / have practiced.

## Scope

- A role- and topic-anchored `SkillAssessmentQuestion` form (or its replacement model), seeded from the imported roadmaps rather than hand-authored per role
- A cap on items per session. Top-level topics run 6–59 per role (MLOps Engineer 9, UX Designer 10, Backend Developer 21, BI Analyst 59), so pick a cap in the 12–15 range and state the selection rule for roles above it
- A mastery source per (session, topic), replacing what `TopicMastery` provided
- Flip `_mastery_gating_enabled()` to `True` and confirm prerequisite gating behaves — it was written as the single switch for this
- Recommendation reasons stated in terms of the topics behind them

## Acceptance criteria

- [ ] Two sessions on different roles receive different question sets, each naming topics from their own roadmap
- [ ] A respondent's ratings change which topic is recommended next; a test asserts two different answer patterns on the same role yield different recommendations
- [ ] Recommended topics are ones the respondent has not mastered, and their prerequisites are satisfied by mastered topics
- [ ] Roles with more top-level topics than the cap still produce a complete, prerequisite-valid sequence
- [ ] A role with no imported roadmap degrades to its curated topics rather than failing
- [ ] `.venv\Scripts\python.exe -m pytest -n auto` and `.venv\Scripts\python.exe -m ruff check .` pass

## Out of scope

- Graded/scored questions with correct answers (rejected in ADR-0002)
- The role-derived readiness target — that is ticket 006
- Role guidance coverage — that is ticket 007
- Removing `data/content/questions/skill/*.yaml`; keep it until this lands, it is the prior art for the item shapes
