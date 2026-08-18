# Skill Assessment measures topic-level self-placement, not general process discipline

**Status:** Accepted

## Context

`CONTEXT.md` defines **Skill Assessment** as the self-assessment that produces **Role Readiness** — "the degree to which a person's current skills and demonstrated experience prepare them to perform a role" — and defines **Recommendation** as "the next Roadmap Topic the product suggests a respondent learn for a specific Role, with a reason."

The implementation does not do either. Walking the live product end to end on 2026-08-18 established the following, all verified in code and against the seeded database:

**The questions are not about skills, and not about the role.**

- All 11 questions are general PSP/SDLC process statements: *"Before building a web feature, I estimate effort, complexity, and delivery time using a repeatable method"*, *"After implementation, I compare actual vs estimated time and document why variances happened"*. None asks about a technology, a topic, or anything on the role's roadmap.
- `SkillAssessmentQuestion` (`assessments/models.py:144-152`) has no foreign key to `Role`. A respondent heading for UX Designer answers exactly the same 11 items as one heading for Backend Developer. The role reaches the assessment only through the Q-learning state key (`skill_assessment_service.py:92-104`), which changes the order questions are asked in — and since all 11 are always asked, that changes nothing about the result.
- 6 of the 8 dimensions are scored from a single Likert item (`sdlc-requirements`, `sdlc-design`, `sdlc-development`, `sdlc-testing`, `sdlc-deployment` have one question each).
- The questions also presuppose professional experience ("after implementation, I compare actual vs estimated time"), while the **Primary Role Discovery Respondent** is defined as a learner who may have none.

**The recommendation is not derived from the answers.**

- The numbered learning sequence on the roadmap page renders `displayTopics` (`app/pages/roadmaps/[sessionId].vue:978-979`) — the role's entire imported roadmap in topological order. Every respondent choosing that role sees the same list regardless of what they answered.
- Only a three-item card consumes the skill-assessment-aware ordering (`RoadmapCompletedOverview.vue:210`, `priorityTopics.slice(0, 3)`), and that ordering is substring keyword matching of dimension keywords against topic titles (`[sessionId].vue:397-436`). Measured against the real imported roadmaps, this finds nothing for most dimensions — 5 of 8 dimensions match zero Backend Developer topics, 6 of 8 match zero Frontend Developer topics — while producing false positives such as `sdlc-deployment` matching UX Designer's *"Deploy Social Proof"*.
- The "To-Be" target the result is compared against is the constant `TARGET_READINESS_SCORE = 78` (`[sessionId].vue:509`), applied flat to every dimension (`RoadmapCompletedOverview.vue:38-43`). The As-Is/To-Be comparison therefore compares the respondent to a fixed regular polygon, identical for every role and every person.
- Role-specific guidance exists for 6 of 26 roles; the other 20 fall back to generic text (`skill_assessment_service.py:75-88`).

**The product used to work the way the definitions describe.**

`data/content/questions/skill/*.yaml` — 26 files, one per role — still sit in the repository. Each asks per topic (*"Can you explain the basic work involved in X?"*, *"Have you practiced a small task related to X?"*) and each answer carries `topic_signals` with a `mastery_delta` of 1.0 / 0.5 / 0.0. That fed `TopicMastery`, which satisfied `TopicPrerequisite.required_mastery_threshold`, which let the recommendation engine pick the next unmastered topic in prerequisite order.

That pipeline was removed. The sockets remain: `required_mastery_threshold` is still on the model, `RECOMMENDATION_MASTERY_THRESHOLD = 0.7` is still in the recommendation service, and `_mastery_gating_enabled()` returns `False` precisely because nothing populates mastery any more. The 26 YAML files are dead — `_load_question_bank` (`roadmaps/seeds.py:58-71`) globs only `questions/role/*.yaml`, and `Question.Stage` no longer has a `skill` member.

## Decision

Skill Assessment asks the respondent to place themselves against **the actual topics of their chosen role's roadmap**, and that placement is what drives the recommendation.

Each item names one topic from the role's roadmap and offers three levels — roughly *never encountered it* / *can explain it* / *have practiced it* — which map to a mastery value for that topic. Mastery satisfies prerequisites, and the recommendation is the next topic the respondent has not yet mastered in prerequisite order, with the reason stated in terms of the topics behind it.

It stays a **self-report**, not a graded test. `CONTEXT.md`'s existing definition ("a self-report of perceived capability, not a test or knowledge check") is unchanged and still governs the wording.

Items are drawn from the **top-level topics** of the imported roadmap, in prerequisite order, capped so no respondent faces an unreasonable number. Top-level topics number 6 to 59 per role (median ≈ 18; MLOps Engineer 9, UX Designer 10, Backend Developer 21, BI Analyst 59), so a cap in the 12–15 range gives coverage without an unfinishable questionnaire.

## Why

Role Readiness is defined per role. An instrument with no role input cannot produce it, and no amount of tuning the 11 items changes that — the defect is structural, not a matter of wording or weights.

Anchoring items to roadmap topics closes the loop the glossary already describes: the same object the respondent rates is the object the roadmap orders and the recommendation names. Readiness becomes a statement about that role's topics, the recommendation follows from the ratings by construction rather than by keyword coincidence, and the "next topic" has a reason that can be shown to the respondent.

It also removes the guesswork layers. No keyword table mapping dimensions onto titles, no flat 78% stand-in for a role's target profile: the target is the role's own topic set, and the gap is the topics not yet mastered.

Keeping it a self-report keeps the cost sane and the promise honest. A graded knowledge check would measure more, but it contradicts the product's own definition, and it would require authoring and maintaining hundreds of scored items per role — a scale this product has no way to sustain.

## Considered Options

- **(Chosen) Topic-anchored self-placement, restoring the mastery pipeline.** Reuses the schema that is still in place, matches the definitions already written down, and makes the recommendation a consequence of the answers.
- **Keep the PSP/SDLC items and weight them per role.** Rejected — weighting eight generic process dimensions per role invents a role profile that no source supports, and the recommendation still would not know which topic the respondent is missing.
- **Improve the dimension-to-topic keyword mapping.** Rejected as a repair of the wrong layer. `topic_group` was considered as a better key than title keywords and does not survive inspection: Backend Developer's groups are `Backend`, `Hashing Algorithms`, and `Visit the DevOps Beginner Roadmap`, and 10 of 26 roles carry a single group for the whole roadmap. It is a layout artefact, not a taxonomy.
- **Make it a graded knowledge check with right and wrong answers.** Rejected — contradicts `CONTEXT.md`'s definition of Skill Assessment, and the authoring and maintenance cost per role is out of proportion to the product.

## Consequences

- `SkillAssessmentQuestion` gains a role- and topic-anchored form; the 8 PSP/SDLC dimensions and their 11 items are retired as the primary instrument.
- `_mastery_gating_enabled()` (`assessments/services/recommendation_service.py`) flips to `True` once a mastery source exists again, restoring prerequisite gating. It was written as a single switch for exactly this.
- `TARGET_READINESS_SCORE = 78` and `DIMENSION_KEYWORDS` in the roadmap page are removed rather than tuned; both are stand-ins for the role-derived comparison this decision provides.
- The 26 files under `data/content/questions/skill/` stay in the repository until the new catalog lands, as prior art for the item shapes and the mastery deltas. They are dead code today and must not be mistaken for the live catalog.
- Role guidance coverage (6 of 26 roles) becomes a content gap to close against the new instrument rather than the old dimensions.
- Until this lands, the product must not claim that Skill Assessment measures readiness *for a role*, or that the learning sequence is personalised. It presently reports engineering-practice self-ratings and shows the role's full roadmap.
