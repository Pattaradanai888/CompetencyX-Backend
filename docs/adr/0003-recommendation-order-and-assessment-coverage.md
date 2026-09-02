# Next-topic recommendation is a deterministic ordering over authored topic sets, not a learned policy

**Status:** Accepted

## Context

Two questions were open at once, and they turned out to be one question: why does the product recommend a topic the respondent has already told us they can do, and why does the roadmap page show every node of the imported graph at once.

Walking the code on 2026-08-23 established the following.

**The recommendation nobody sees is the only one derived from the answers.** `GET /assessment-sessions/{id}/skill-assessment` already returns `topic_mastery` and `recommended_topics`, ordered weakest-first with topics at or above the threshold dropped (`assessments/services/topic_skill_assessment_service.py`). Neither field is read anywhere in the frontend. What the roadmap page actually ranks by is `DIMENSION_KEYWORDS` substring matching (`app/pages/roadmaps/[sessionId].vue:400-436`) — the layer ADR-0002 decided to delete.

**Nothing in the Q-learning was learning.** `ASSESSMENT_RECOMMENDATION_POLICY` was `'q_learning'` in `config/settings/base.py`, so the policy ran on every answer submission and every results read.

- `_calculate_recommendation_reward(topic)` is `0.7 + 0.2/(1 + display_order) + difficulty_bonus` — a function of the topic alone. It never observes an outcome, and it is paid at selection time. The Q-values therefore converge on a fixed function of `display_order`, which is precisely the topic the rule-based policy already picks.
- The state key carries `mastery-{bucket}` and `weak-{bucket}`, but `mastery_scores` is always `{}`, so `average_mastery` is always `0.0` and `weak_topic_count` always saturates the bucket cap. Two of the state dimensions are constants.
- The delayed signal, `_calculate_skill_assessment_outcome_reward`, is the mean of the respondent's own ratings less a spread penalty. It rewards recommending to people who rate themselves highly, which is not a property of the recommendation.
- The question-selection policy rewards `(answer_value - 1) / 4`, so it learns to ask the items a respondent agrees with most. An adaptive questionnaire needs the opposite: the item that resolves the most uncertainty.
- `RecommendationQValue` held 1 row across 12 sessions. `app/utils/roadmaps-q-learning.ts` (278 lines, a third implementation) is imported by no file.

**"Not asked" and "cannot do" were the same value.** `mastery.get(slug, 0.0)` collapses them. `select_assessable_topics` filters `node_type == 'topic'` — described in its own comment as taking top-level topics, which is a different predicate — and caps at 12. Cyber Security Engineer/Analyst is therefore assessed with 6 items against 301 nodes, and Backend Developer is never asked about Git, PHP, Go, or JavaScript, because those nodes carry `node_type='subtopic'` with a null parent.

**The imported graph cannot support inference.** Of 3,367 nodes: 2,112 of 2,811 `subtopic` nodes have no parent, and 2,152 nodes (64%) appear in no edge at all. Propagating a rating up prerequisites or down to children reaches roughly a fifth of the graph.

## Decision

**1. No reinforcement learning anywhere in the product.** The Q-learning policy is off (`ASSESSMENT_RECOMMENDATION_POLICY = 'rule_based'`), and the three implementations, their tables, and their settings are removed. Recommendation order is deterministic and explainable on the first session.

**2. The assessment is anchored to authored Assessable Topic Sets, not to raw roadmap nodes.** Each role gets roughly 15–20 sets, each mapping to a set of nodes in that role's imported graph. Sets are drafted by an LLM and reviewed before they go live; the catalog is gated by the persona-fidelity harness like the rest of the content. Full node coverage is not required — nodes that land in no set are flagged for review rather than blocking the catalog.

**3. Recommendation order is: prerequisite layer, then `display_order`, then Self-placed Mastery.** Prerequisites always win. Where the graph carries no edges — 64% of nodes — `display_order` stands in for prerequisite order, on the grounds that the roadmap's author sequenced it deliberately. Self-placed Mastery only breaks ties inside a layer.

**4. An Unassessed Topic is never presented as a gap.** Assessed sets that fall below threshold are recommended first. Unassessed sets follow, in roadmap order, labelled as not assessed and each carrying an inline control to mark it Held. The respondent closes the coverage gap at the moment they see it.

**5. The questionnaire stops when the top five recommendations stop moving,** with a floor of 12 items and a hard ceiling of 20. Hitting the ceiling without stability reports low confidence rather than asking further.

**6. After the assessment, the respondent sees the next three to five topics, not the roadmap.** The full graph moves behind an explicit "see the whole roadmap" action.

**7. Marking a topic Held requires a user account.** Marks belong to the person, not the browser, and must survive a device change.

## Why

Every layer that guessed is replaced by a layer that states its evidence. A learned policy whose reward is a function of the action alone cannot outperform the rule it was meant to improve on, and one whose reward is the respondent's self-esteem optimises the wrong thing entirely; keeping either would mean carrying the machinery and the cold-start problem to reproduce a sort. The graph's own structure was the other candidate source of inference and it does not hold up under measurement, which is why the assessable unit is authored rather than derived. And separating Unassessed from low mastery is what makes "ask few questions" honest: the product asks about a fraction of the roadmap and says so, instead of reporting the unasked remainder as absent capability.

## Considered Options

- **Fix the reward functions and keep Q-learning.** Rejected. A real reward needs a real outcome — a thumbs-up, or the respondent following the order we proposed — and with 12 sessions there is no data to learn from either way. The deterministic rule is what the learned policy would converge on.
- **Train the policy offline against the persona harness.** Rejected as the primary answer: it learns the simulator. It stays available if a genuine outcome signal is ever instrumented.
- **Infer held topics through the roadmap graph (parent implies children, follow-on implies prerequisites).** Rejected on the numbers above.
- **Use `topic_group` as the assessable unit.** Rejected in ADR-0002 and re-checked here; it is a layout artefact.
- **Switch the assessable unit to root nodes (`parent_id is null`).** Rejected — it moves the pool to 100–294 per role (median 100.5), which makes "the first 12" less meaningful, not more.
- **Ask about every set.** Rejected against the requirement to ask few; superseded by the stability rule.
- **Paginate the roadmap endpoint.** Rejected. The complaint was that 301 numbered steps are unusable, which paging does not fix, and the payload is master data that changes only on import — a smaller "next topics" response plus caching addresses both halves.
- **A durable anonymous token instead of accounts.** Rejected: a mark that a cleared browser destroys is not a statement about the person.

## Consequences

- `Recommendation`, `RecommendationQValue`, `SkillAssessmentQuestionQValue`, `SkillAssessmentFeedbackEvent` (the ledger that kept the Q update at most once per question), `assessments/services/q_learning.py`, `assessments/services/recommendation_service.py`, the `ASSESSMENT_RECOMMENDATION_POLICY` and `ASSESSMENT_RECOMMENDATION_Q_*` settings, and `app/utils/roadmaps-q-learning.ts` are removed. `preferred_path_recommendation` / `best_fit_path_recommendation` disappear from the results payload.
- `DIMENSION_KEYWORDS`, `TARGET_READINESS_SCORE`, and the keyword-priority list in `app/pages/roadmaps/[sessionId].vue` go with them, completing the deletion ADR-0002 called for.
- `select_assessable_topics` — the `node_type == 'topic'` derivation and its cap of 12 — is removed once every role has authored sets. A role with no sets is served the role-independent items, never items read off its roadmap.
- Authoring 15–20 sets for **all 26 roles** in one pass — no pilot subset — with reviewed Canonical Thai wording, is the largest single item of work here and the critical path. It is a content bottleneck, not a code one, and it sits on top of a review queue that already holds 58 questions and 26 roles.
- Accounts are new surface area for a product that has had no authentication at all, and they land **first**: sessions become owned before the recommendation work is built on top, so no session has to be migrated from anonymous ownership afterwards. The cost is that the recommendation ordering the respondent is actually waiting on ships behind an authentication build.
- Nodes belonging to no Assessable Topic Set stay Unassessed indefinitely and are reported as a review backlog.
