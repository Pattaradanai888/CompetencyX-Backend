# Questionnaire review — Role Discovery and Skill Assessment

**Reviewed:** 2026-08-18, against the seeded database (58 active Role Discovery items, 284 topic-anchored Skill Assessment items, 11 fallback items).

Every count below is measured, not estimated. The yardstick is `CONTEXT.md`, which defines the **Primary Role Discovery Respondent** as "a learner or early-career explorer who may have little or no professional technology-work experience", and requires **Experience-Neutral Questions** that "describe recognizable work activities in plain language, so a Primary Role Discovery Respondent can express a preference without needing technical vocabulary or prior job experience".

---

## Role Discovery — 58 items

### 1. Ten items have no Thai wording at all

`CONTEXT.md` defines the **Canonical Thai Question** as "the reviewed Thai wording that defines the meaning of a Role Discovery question", with other languages as adaptations. These ten items therefore have no definition of what they mean — the English is supposed to be the adaptation, not the source:

`role-swebok-37-mobile-native`, `38-backend-platforms`, `39-database-dba`, `40-blockchain`, `41-game-client`, `42-game-server`, `43-tech-docs`, `44-bi-analytics`, `45-ml-platform`, `46-devrel`

They are consecutive (37–46), so this looks like one batch that was added and never carried through review. **This is the most concrete defect in the set** and the cheapest to fix.

### 2. The vocabulary assumes the respondent has already worked as an engineer

38 of 58 items (66%) contain workplace or practitioner vocabulary. The most frequent terms are `api` (11 items), `pipeline` (10), `sprint` (7), `stakeholder` (5), `database` (4), `integration` (4), `release` (4).

The worst offenders stack several at once:

> **role-swebok-18** — "When resources are limited, I secure zero-downtime **deployment pipelines** and **API** security over polishing the visual UI for **stakeholders**."

> **role-swebok-02** — "Before coding a complex system, I refuse to start building screens until I've mapped the **database schema** and **integration** boundaries, even if **project managers** demand a quick UI demo."

The 20 items the keyword scan called clean are mostly not clean either — the scan simply lacked the words. They include "JVM garbage collection", "solidity smart-contract logic", "consensus mechanisms", "rendering lifecycles", "CRUD applications", "git merge conflicts", "spaghetti code". Treat the honest figure as close to all 58, not 66%.

A student who has never held the job cannot answer these from preference. They will answer from guesswork or from whichever option sounds more impressive, and the evidence the product collects is then not the preference evidence it claims to be.

### 3. Nearly every item is a forced trade-off between two unfamiliar things

- 37 of 58 (64%) are phrased as "I would rather X than Y" / "X more than Y"
- 27 of 58 (47%) add a concession clause ("even when the team…", "even if the deadline…")
- Median length is 23 words, longest 29

So a typical item asks the respondent to weigh two activities they may not recognise, under a condition that adds a third consideration, in one 23-word sentence rated on a five-point agreement scale. Being unable to picture an activity is not the same as having no preference between activities — `CONTEXT.md` makes exactly this distinction, and the current phrasing collapses the two.

### 4. Absolute wording pushes answers toward the middle

11 of 58 (19%) use "I refuse to…", "I strictly enforce…", "never", "always", "my entire day". Few people agree strongly with an absolute, so these items compress toward neutral and lose the ability to separate respondents — which is the one thing a discovery item has to do.

### Recommended order of work

1. **Write the ten missing Thai items** (37–46). Without them those questions have no canonical meaning. Half a day.
2. **Rewrite the vocabulary** so each item names an activity rather than a technology. "I'd rather figure out why something is slow than design how it looks" carries the same signal as the API/pipeline phrasing without requiring the job.
3. **Split the trade-offs.** One activity per item, rated on its own. The trade-off can be recovered from the scores; it does not have to be inside the sentence. This also shortens items toward 12–15 words.
4. **Drop the concession clauses and the absolutes.** They add reading load and compress the scale.

Items 2–4 are a rewrite of the bank, not an edit pass — plan it as content work with its own review, and keep the existing items running until replacements are reviewed.

---

## Skill Assessment — 284 topic items across 26 roles

These are the items introduced on 2026-08-18 (ADR-0002), generated from each role's imported roadmap. They are a large improvement on what they replaced — they name the role's own topics, and Thai wording is complete (0 missing). Three things still need attention.

### 1. Seven assessed "topics" are instructions, not skills

The roadmap graphs contain navigational nodes that read as tasks for the reader. Generated into an item, they produce nonsense:

`Pick a Language`, `Pick a Framework`, `Learn SQL`, `Learn a Programming Language`, `Learn a Programming Lang.`, `Learn the Fundamentals`, `Roadmapping Tools`

> "I could work on **"Pick a Language"** in a real project without help."

Fix at import: skip nodes whose titles are imperative (`Pick …`, `Learn …`, `Visit …`) or rewrite them to the underlying skill. Cheap, and it removes the most obviously wrong thing a reviewer would see.

### 2. One template for every item, so there is no difficulty gradient

Every item is `I could work on "{topic}" in a real project without help.` Rating "Docker" and rating "Design and Development Principles" therefore ask the same thing at the same depth, though one is a tool and the other a body of judgement.

The retired per-topic bank had two levels — *can you explain it* and *have you practiced it* — which is a better instrument for placement, because a learner sits between them. Consider restoring that pairing for the topics that matter most, rather than one item per topic.

### 3. Some titles do not survive being dropped into a sentence

Titles run to 38 characters and carry punctuation from the diagram: `Schema Design Patterns / Anti-patterns`, `Release Notes / Product Announcements`, `Containerization vs Virtualization`. They read acceptably in a list and awkwardly mid-sentence. Either normalise titles at import or use a template that sets the topic apart on its own line.

### Recommended order of work

1. **Filter the imperative node titles at import** — an hour, and it removes the items a reviewer would most likely notice.
2. **Decide whether one item per topic is enough**, or whether the explain/practice pairing comes back for the top topics.
3. **Normalise long or punctuated titles** for use inside a sentence.

---

## What is not wrong

Worth stating, so effort goes where it is needed:

- Thai coverage on the Skill Assessment is complete, and the five-point scale is translated on both instruments.
- The Role Discovery bank has a clear structure — 46 core items plus 12 tie-breaks — and each item carries its dimension signals and a discrimination score, so a rewrite has somewhere to anchor.
- Skill Assessment items are now generated from role content rather than hand-maintained per role, so fixing the generator fixes all 26 roles at once.
