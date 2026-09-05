# Recommendation Stability is decided by lookahead over the answers, not by comparing saves

**Status:** Accepted (2026-09-05)

## Context

ADR-0003 decision 5 stops the Skill Assessment "when the top five recommendations stop moving", with a floor of 12 items and a ceiling of 20. The implementation defined "stop moving" as *the top five after this save equals the top five after the previous save*, and stored that verdict on the session (`skill_assessment_stable`, `skill_assessment_top_five`).

The frontend never saved between answers. It asked `POST …/skill-assessment/next-question/` with the answers it held locally and saved once, at the end. Against saved state that was always empty, `settled` was always false, so every respondent answered every set, the floor and the ceiling were the only things that ever ended the questionnaire, and every completed assessment reported `confidence: "low"`. The backend's own stop-rule tests passed because they saved after each answer. Had any role carried more than 20 sets, the frontend would have stalled at the twentieth answer without an error, because it refused to submit until every item was answered.

The comparison-of-saves definition was also weak on its own terms: an answer that happened not to move the top five counted as settled even when the very next answer would have.

## Decision

1. **Recommendation Stability is a pure function of the answers handed in.** The suggestions have settled when no single unanswered set, rated at any point on the scale, would change the next five topics. The rule reads only the answers it is given, so `next-question` decides it for answers a client has not saved, and the save endpoint applies the same rule to the answers it is asked to complete with. Nothing about stability is stored on the session.
2. **The floor and ceiling stand as in ADR-0003.** Below the floor the assessment keeps asking however settled it looks; at the ceiling it stops however unsettled. A catalog with nothing left to ask is settled vacuously, so a fully answered small catalog completes with high confidence.
3. **The client stops when the backend says so.** `next_question: null` is the signal to submit; the client neither requires every item to be answered nor picks a question of its own when the backend cannot be reached. The client-side candidate scorer is removed.
4. **The role-independent PSP/SDLC items are retired**, as are the `recommendations` app, the 26 legacy `questions/skill/*.yaml` files, the PSP/SDLC "track" on radar axes, and the frontend's PSP/SDLC evaluation layer. Every curated role has authored Assessable Topic Sets (a test guards it); a role without them is served an empty assessment, not items about nothing in particular.
5. **Nothing in the results payload names topics to learn unless it came from the answers.** The "Focus next on X, Y, Z" sentence and `preferred_role_gap_topics`, which listed the first three curated topics regardless of what was answered, are removed. The Recommendation lives on the skill-assessment state, with its reason.
6. **Every topic state carries the `node_slugs` its set covers**, so a roadmap view marks a held set's nodes by slug rather than by matching titles (which matched 70 of 456 sets).

## Why

A stop rule that the real client cannot trigger is not a stop rule. Making stability stateless removes the protocol coupling that broke it: the backend no longer needs the client to save in a particular rhythm, and a client proposing answers gets exactly the verdict it will get on save. The lookahead definition is also the literal reading of the glossary — "further answers stop changing which topics the product would suggest next" — where the previous definition only sampled it. It costs at most (unanswered sets × 5 ratings) re-orderings of at most 20 items per request, on a graph read once.

Retiring the fallback items follows from ADR-0002 and ADR-0003: with every role authored, the only thing the fallback could do was quietly serve an instrument that measures readiness for no role. The client-side scorer goes for the same reason ADR-0003 removed the learned policy: an order that does not come from the backend's evidence is a guess.

## Considered Options

- **Have the frontend save after every answer** and keep the comparison-of-saves rule. Rejected: it doubles requests, keeps the protocol coupling, and keeps a definition that can settle one answer early.
- **Send answers as an ordered list and replay the sequence server-side.** Rejected: it still compares consecutive states, and it forces a payload shape change for a weaker rule than the lookahead.
- **Keep the fallback items for a future role without sets.** Rejected: no such role exists, a test forbids one, and the items measure readiness for no role.

## Consequences

- `skill_assessment_stable` and `skill_assessment_top_five` are dropped; `SkillAssessmentDimension.track` is dropped; role-independent `SkillAssessmentQuestion` and `SkillAssessmentDimension` rows are deleted by migration (answers to them keep their rows, keyed by slug).
- `topic_states[]`, `recommended_topics[]` and `next_topics[]` gain `node_slugs`; `preferred_role_gap_topics` leaves the results payload; the catalog `version` moves to `2026-09.topic-sets-v1`.
- The frontend submits when `next_question` is `null`, reads `progress` from that response, and marks held nodes on the roadmap by slug.
- `confidence` is now meaningful: `high` when the suggestions settled or nothing was left to ask, `low` only when the ceiling ended the assessment.
