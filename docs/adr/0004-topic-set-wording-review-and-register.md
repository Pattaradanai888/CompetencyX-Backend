# Topic-set wording is reviewed per set, served while draft, and written in the role's working vocabulary

**Status:** Accepted (2026-08-26)

## Context

Issue #7 makes the Canonical Thai Wording of every Assessable Topic Set a human gate. The code had no representation of that gate: `validate_topic_set_catalog --strict` treated a non-empty `title_th` as "reviewed", so 459 LLM-drafted strings passed strict validation the moment they were written. `data/content/questions.yaml` already carries a per-item `review.status`, so the two catalogs disagreed about what "reviewed" means.

At the same time, `CONTEXT.md` defines the respondent as a learner with little or no work experience and requires Role Discovery questions to be Experience-Neutral. Read literally, that rule would push topic-set wording toward plain Thai with no tool names, which is the opposite of what the drafted sets contain.

## Decision

1. **Approval is per set and recorded in the YAML** as `review.status: draft | reviewed`, mirroring `questions.yaml`. Strict validation gates on the status, never on the presence of `title_th`. An agent may write draft wording into `data/content/topic_sets/` but never sets the status to `reviewed`.
2. **A draft set is asked, with its draft Thai wording, and the respondent is not told it is draft.** Review runs in parallel with use. This is accepted because the catalog is on staging with developers as the only respondents; the consequence that a wording change reinterprets earlier answers is explicitly out of scope until there are real respondents.
3. **Topic-set wording uses the working vocabulary of the role, tool names included.** Terms practitioners keep in English (Machine Learning, Deploy, Secret, Stakeholder, Reactive Programming, Configuration Management) stay in English; the security register is ความปลอดภัย, not ความมั่นคงปลอดภัย; parentheticals name 2–3 representative tools or standards. The Experience-Neutral rule applies to Role Discovery only.
4. **Only practisable skills are sets.** Industry exposure, certifications, and career logistics are removed even when the imported roadmap lists them; their nodes join the review backlog.
5. **A set that bundles two skills that rarely co-occur is narrowed, not split or kept.** The secondary skill's nodes and wording are dropped to the backlog (Objective-C from the Swift set, reverse ETL from data pipelines, RUP/PRINCE2 from delivery methodologies).
6. **The 15–20 band in ADR-0003 is a target, not a validation gate.** AI/Data Scientist stays at 8 sets because its imported roadmap has 8 nodes.

## Why

A respondent who does not recognise a term has, by that fact, told us the topic is not Held — which is the correct answer for a learner, and exactly the anchor a respondent who already has the role in mind needs. Plainer wording would blur both. Separating "reviewed" from "has wording" is what lets the catalog be used and reviewed at the same time without pretending the gate was passed. Cutting non-skill sets and narrowing bundled ones keeps every set answerable with one rating without inflating counts past the band.

## Considered Options

- **Reviewed = non-empty `title_th`** (the code as found). Rejected: it makes the human gate unrepresentable.
- **Hold draft sets back, serve English titles, or label them draft.** Rejected: an empty assessment or an English prompt inside a Thai questionnaire is a worse staging experience than draft Thai, and there are no external respondents yet.
- **Experience-neutral wording for topic sets.** Rejected: see Why.
- **Split bundled sets.** Rejected: it pushes large roles past 20 and multiplies the review queue.
- **Hand-author non-roadmap sets or borrow nodes from a neighbouring role for AI/Data Scientist.** Rejected for now: a set with no roadmap nodes has nothing to mark Held.

## Consequences

- `validate_topic_set_catalog`, `assessable_topic_set_service`, and the seed loader gain `review.status`; the comment at `topic_skill_assessment_service.py:129-133` that argues against serving unreviewed Thai is rewritten to match decision 2.
- Before any real respondent uses the product, decision 2 must be revisited: either every set is `reviewed`, or the answer-invalidation question (what happens to Self-placed Mastery when wording changes meaning) gets an answer.
- `docs/topic-set-thai-review.md` §2 is resolved by decision 3 and can be applied mechanically; §3 is resolved by decisions 4–5.
