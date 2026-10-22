# Role Discovery is adaptive, asks at most 25 short items, and shows three Role Candidates

**Status:** Accepted (2026-10-21); the scoring rule and the 3.5-vote resolve margin are amended by ADR-0007

## Context

Role Discovery asked all 46 core items in a fixed order, then tie-breaks gated on the top pair, about 46 items per respondent before the Skill Assessment's 12–20. The items themselves were the larger problem (`docs/questionnaire-review.md`): a median of 159 Thai characters, workplace-conflict scenarios ("even when the PM pressures you…"), English jargon in 46 of 48 Thai prompts, ten items with no Thai at all, and wording that read as machine-translated, against `CONTEXT.md`'s Experience-Neutral and Single-Axis Question.

The noisy-persona harness reported 0.947 top-1 for that bank, but its personas answer every item from one role profile with light noise. A second harness, `simulation/realistic_personas.py`, models people more like survey respondents: preferences blended from one to three roles, response styles (acquiescence, midpoint, extreme), 8% careless responders, unfamiliar vocabulary, social desirability and fatigue, calibrated where the literature gives numbers (careless share; per-item retest noise of 0.7–0.9 scale points) and swept over eight assumption scenarios where it does not. Under it the old bank names the respondent's closest role first only 32% of the time and among its top three 59% of the time. No variant of the 26-way problem got above roughly 0.5 top-1 under realistic answering, so a single declared role is the wrong thing to show most people.

## Decision

1. **The bank is rewritten Thai-first: 31 core items and 13 tie-breaks, 44 in all.** Each names one activity or one domain in everyday words, 43 characters median and 73 at most, with no conflict scenario, absolute or forced slang. Wording went through a round of eight reviewer agents (student, Thai editor, psychometrics and role-mapping lenses, each on two models) and a second round of four; blind construct mapping agreed with the authored constructs at Fleiss κ 0.88. Every item stays `review.status: draft` until a person approves it.
2. **Core and tie-break items form one pool.** `item_group` and `discriminates_between` keep recording what an item was written for; the flow no longer reads them.
3. **The flow is adaptive.** Everyone first answers eight warm-up items in a fixed order (web, mobile, games, AI, numbers, security, writing, product). After that the next item is the one whose strong-agree votes most disagree across close pairs among the six leading roles: a pair straddling the boundary of the three shown candidates counts fully, a pair inside them counts half, each weighted by `exp(-vote gap / 2)`. Ties go to the lower display order. Scoring stays sign-vote counting.
4. **The stop rule:** at least 12 answers; stop once the third candidate leads the fourth by 4 votes; stop at 25 answers regardless. A pool smaller than the floor is asked to the end.
5. **Three Role Candidates are shown.** Insights and results carry `role_candidates`, the top three ranked roles, once the survey is complete. `milestones.max_role_questions` reports the cap for a progress indicator.
6. **"Resolved" needs a 3.5-vote lead** of the best fit over the runner-up (was 2.5). Most sessions now finish `low_confidence`, which is the honest outcome, and present their candidates rather than a verdict.

## Why

On the realistic harness, across eight scenarios, 1,500 respondents each, the shipped flow (measured through production code) against the old one:

| | old bank, fixed | new bank, this flow |
|---|---|---|
| questions asked | 46 | 24.9 |
| top-3 contains closest role (mean / worst scenario) | 0.587 / 0.534 | 0.629 / 0.597 |
| top-1 | 0.32 | 0.40 |
| resolved but outside the respondent's top two (worst scenario) | 3.1% | 1.3% |
| retest overlap of the three shown | 0.373 | 0.378 |

On the noisy-persona harness it keeps 0.935 top-1 (floor 0.88) and 0.995 top-3, with precision 1.0 when resolved.

The configuration was chosen from a staged search: 724 combinations of pick rule, warm-up, stop rule and ranking at 1,000 respondents each; the best 34 under all eight scenarios with retest; then length and scoring levers; then every finalist under both harnesses. The rule adopted is the one that held up in both worlds rather than the one that won in either.

## Considered Options

- **Fixed order with the stop rule only.** Saves about three items; the stop rule rarely fires before the informative domain items are reached.
- **Strict lookahead stop** (stop when no remaining answers can change the candidates). Asks 33–38 items once tie-breaks share the pool.
- **"Top role unchanged for k answers."** Flips the result for 9–21% of respondents.
- **Bayesian ranking with information-gain picks.** About five points lower top-3 than sign votes.
- **Continuous-magnitude scoring with an optimised fixed order** (20–22 items). Best of all on the realistic harness (top-3 0.70, retest 0.40), but the realistic harness generates answers from the same continuous overlap that this scoring uses, and on the noisy-persona harness it drops to 0.67 top-1. Rejected until real answers can decide which world respondents live in.

## Consequences

- Answers stay recorded as raw scale values, so once a few hundred real sessions exist the magnitude-scoring option and the stop thresholds can be refit on them instead of on simulators.
- Retest overlap is about 0.38 in every design tried: the same person retaking the survey keeps roughly one of three candidates. That limit comes from per-item reliability, not from the flow, and is the next thing worth working on.
- `simulate_personas --model realistic` reports the realistic harness; the persona baseline is re-pinned with this change.
- The core bank must still signal every SWEBOK knowledge area; the balance test now asks for each at least once, since separation is measured by the harnesses rather than by item counts per area.
- The frontend shows three candidates and cannot know the survey length in advance; it reads `next_question: null` as the end, as before.
