# Role votes carry a relevance share, and best-practice items ask about time spent

**Status:** Accepted (2026-10-22)

## Context

A respondent who took Role Discovery for real answered strongly for building websites, security, finding weak spots and hunting bugs, and lukewarm or against every AI item, and was shown Machine Learning Engineer, MLOps Engineer and PostgreSQL DBA. The top three had exactly 5.0 votes each; Machine Learning Engineer came first only because its slug sorts first, and Cyber Security was seventh at 4.0. Two things combined.

**Best-practice items.** Seven of that respondent's 25 answers were strong agreement with statements such as "when a task is repetitive I want to automate it", "I like trying two approaches and seeing which works better" and "I would like a security check every time before an app is released". Alongside the real session, 8 and then 26 LLM role-play respondents (Haiku, each playing one person described by background and tastes, never by job title) answered the bank. Automation averaged +1.89 and nobody disagreed; evidence, testing, requirements, data storage, cost/value, architecture and the secure-pipeline tie-break all averaged above +1.1 with almost no disagreement. These items asked whether something is good practice, so disagreeing read as admitting to being a careless worker, and anyone who had studied software agreed. That is the respondent's own complaint, and the role-play respondents flagged the same items as ones where "disagree" would make them look bad (66 flags on the 15 worst items).

**Sign votes.** A role received a full vote from any answer whose chosen side overlapped its profile at all. The security item gave PostgreSQL DBA and MLOps, which carry security at the secondary level, the same +1 as Cyber Security. Broadly profiled roles (MLOps, Machine Learning, Full Stack, PostgreSQL DBA touch 11–13 dimensions) therefore collected a vote from nearly every item a respondent agreed with, and agreeing with many items is exactly what the best-practice items produced.

The two harnesses could not settle the scoring question by themselves: noisy personas answer by the sign of the profile overlap, which is what sign votes count, and realistic personas answer by its magnitude, which is what magnitude scoring counts, so each favours its own rule (ADR-0006 rejected magnitude scoring for this reason). The role-play panel and the real session are the evidence from outside both.

## Decision

1. **Each answer moves each role by `strength × (½·sign(s) + ½·s / max|s|)`**, where `s` is the overlap of the chosen side with the role profile minus the overlap of the rejected side and `max|s|` is taken over all roles for that answer. The role an item is most about still gets a full vote; a role that only brushes it gets a part of one. `ROLE_SIGN_VOTE_SHARE = 0.5`. The adaptive pick reads the same per-answer scores, so ranking and picking stay on one rule.
2. **Margins are rescaled.** Leads are about 30% smaller under the relevance share, so the resolve margin moves from 3.5 to 2.5 and the full-confidence margin from 5.0 to 3.5; at 2.5 about 5% of sessions resolve and about 1% in the worst scenario resolve to a role outside the respondent's top two, the trade-off 3.5 gave before. The stop rule (12-item floor, third candidate 4 votes clear of the fourth, 25-item cap) is unchanged: varying it moved nothing.
3. **Eighteen items are reworded to ask what the respondent would want to do rather than whether something is good practice or merely interesting**: automation, evidence, data storage, testing, requirements, cost/value, operations, maintenance, process, construction, security, infrastructure and reports, and the secure-pipeline, train-own-model, predict, screen-versus-server and business-questions tie-breaks. Constructs and signals are unchanged. The first wordings named the effort ("a whole day…"); a blind review by a model from another family pointed out that this measures stamina instead, so testing, automation and train-own-model were reworded again around a concrete activity. Explore-data, model-in-production, blockchain, AI-in-use, explaining, leading, server and the warm-up AI item keep their wording because every alternative tried fitted worse or was not understood.
4. The realistic harness gains `best_practice` (agreement pull of 0.8 on the fourteen items the panel agreed with regardless of taste) and `acquiescent_heavy` (60% acquiescent responders, shift 0.4–0.9).
5. The authoring checklist asks for items a respondent can disagree with without losing face.

## Why

Realistic harness, ten scenarios × 1,500 respondents, through production code:

| | ADR-0006 (sign votes, old wording) | sign votes, new wording | **relevance share, new wording** |
|---|---|---|---|
| top-3 contains closest role (mean / worst) | 0.615 / 0.549 | 0.614 / 0.558 | **0.662 / 0.594** |
| top-1 | 0.393 | 0.401 | **0.449** |
| resolved but outside the top two (worst) | 1.27% | 1.33% | **0.73%** |
| retest overlap of the three shown | 0.381 | 0.375 | **0.407** |

The wording barely moves this harness, which models wording only through length and jargon; the wording evidence is the panels below.

Noisy-persona harness: top-1 0.924 (was 0.935, floor 0.88), top-3 0.989, precision when resolved 1.0.

Role-play panel, 26 respondents (one designed per role) replayed through the adaptive flow on the second-round wording: the designed role is among the three shown for 17 (sign votes: 11 on the old wording, 13 on the new). The real respondent's 25 answers now rank DevSecOps first, with Machine Learning out of the top three; it is kept as a regression test.

Wording was chosen in three rounds, each comparing alternatives blind within one run. Rounds one and two (Haiku): on the first thirteen reworded items the mean answer fell from +0.32 to −0.02, "would look bad to disagree" flags fell from 66 to 36, and the correlation between an answer and how central the item is to the respondent's designed role rose from 0.35 to 0.39. Between rounds, a model from another family rated all 44 items and the thirteen old/new pairs blind; it preferred the new wording in ten pairs and named two problems the panel had missed: effort words that measure stamina, and "I am curious how X works" items that measure an onlooker's curiosity rather than wanting to do the work. Round three (Sonnet) tested alternatives for seventeen items against those points and kept eight, chosen by the same correlation, for example security from 0.52 to 0.82, automation from 0.48 to 0.68 and train-own-model from 0.27 to 0.51.

## Considered Options

- **Magnitude only.** Best on the realistic harness (top-3 0.670) but 0.742 top-1 on the noisy one.
- **A larger magnitude share (65–75%), or sign votes plus raw magnitude.** A smooth trade: each step toward magnitude gains realistic accuracy and loses noisy accuracy (0.90–0.91 at 75%); raw magnitude also leaves per-answer movement unbounded. Half and half held up in both harnesses and ranked best on the panel.
- **Centring each respondent's answers on their own mean.** Helped the role-play respondents but made the real respondent's result worse.
- **Votes only for roles with at least half or three quarters of the strongest relevance.** Worse in every world.
- **Choosing one of three or four activities per screen** instead of agreeing with statements. The standard remedy for agreement and desirability bias, but it changes the API and the frontend; left for a later decision.

## Consequences

- `fit_score` values are fractional rather than multiples of 0.5.
- Insights and results are recomputed from stored answers on every read, so a session completed before this change shows candidates under the new rule while its stored `best_fit_role` stays as it was until another answer is submitted.
- The role-play panel is evidence from neither harness but still not from people: LLM respondents agree more readily than people do, and the designed roles are an author's judgement. The real-session regression test and future pilot data outrank it.
- Both harnesses remain circular in opposite directions; a future change to the scoring rule needs evidence from outside both, as this one had.
