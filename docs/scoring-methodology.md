# Role-Discovery Content Methodology

This document defines how every number in the role-discovery system is
derived, so that a human can audit or re-derive any weight without trusting
the person (or model) who typed it. **No numeric weight may be hand-edited**;
humans edit ordinal levels and rationales, and code derives the numbers.

## The traceability chain

```
runtime weight
  → ordinal level            (role_dimension_relevance.yaml / question signals)
    → rationale + sources    (per cell / per question)
      → committed extract    (data/sources/swebok_v4_ka_reference.yaml,
                              data/upstream/roadmap_sh/*.json + manifest.yaml)
        → external document  (SWEBOK Guide v4.0; roadmap.sh)
```

A claim is **grounded** when its cell/question is `review.status: reviewed` —
meaning a human has checked the rationale against the committed source. Cells
still at `draft` are LLM-proposed and must not be treated as validated.

## Dimension registry

The 38 scoring dimensions are defined in `roadmaps/questionnaire.py`:

- **18 SWEBOK knowledge areas** (KA1–KA18) — anchored one-to-one to
  `data/sources/swebok_v4_ka_reference.yaml`.
- **8 role families** — coarse clusters (application_build, backend_platform,
  data_ai, operations_security, leadership_process, people_product,
  documentation_practice, game_family) used to separate roles whose KA
  footprints overlap.
- **12 specialization endpoints** — platform/domain markers (web_frontend,
  server_backend, android_platform, …) that identify a role family member.

## Rubric ladders (the ONLY places numbers are defined)

### Role × KA (`meta.weight_ladder.ka` in role_dimension_relevance.yaml)

| Level | Weight | Definition |
|---|---|---|
| `core` | 1.0 | A top knowledge area of the role: daily, identity-defining work. Must correspond to the role's `top_ka_codes`. |
| `supporting` | 0.6 | Regularly practiced as part of the job, but not what defines the role. |
| `peripheral` | 0.3 | Touched occasionally, usually via tooling or adjacent collaboration. |
| (absent) | 0.0 | Not part of the role's working profile. |

### Role × family (`meta.weight_ladder.family`)

| Level | Weight | Definition |
|---|---|---|
| `primary` | 1.0 | The family that best describes the role. |
| `secondary` | 0.7 | A family the role genuinely straddles. |

### Role × specialization (`meta.weight_ladder.specialization`)

| Level | Weight | Definition |
|---|---|---|
| `defining` | 1.0 | The endpoint that names the role. |
| `shared` | 0.7 | An endpoint the role shares with its neighbors. |

### Question signal strength (`SIGNAL_STRENGTH_WEIGHTS` in questionnaire.py)

| Level | Weight | Definition |
|---|---|---|
| `primary` | 1.0 | The construct the item was written to measure. Exactly one per question, equal to its `construct` field. |
| `secondary` | 0.6 | A dimension an agreeing respondent plausibly also endorses. |
| `contrast` | 0.3 | The dimension the statement trades against (usually on the disagree side). |

Rationale for three steps: scoring is vote-based
(`assessments/services/scoring_service.py`) — per answer per role only the
**sign** of `overlap(chosen side) − overlap(rejected side)` matters, so finer
ladders add authoring burden without measurable benefit (verified by the
ablation that led to vote scoring, 2026-07).

## Derivation pipeline

```
data/content/role_dimension_relevance.yaml   (humans edit levels + rationale here)
        │  manage.py generate_role_weights
        ▼
roadmaps/role_weights_generated.py           (GENERATED — never hand-edited)
        │  import
        ▼
roadmaps/questionnaire.py ROLE_PROFILE_WEIGHTS
        │  import (Django-free)
        ▼
assessments/services/scoring_service.py      (vote counting)
```

Guards:
- `manage.py generate_role_weights --check` fails if the generated module is
  stale relative to the mapping (also enforced by a pytest drift test).
- Catalog validators enforce: levels only (no free numbers), source refs must
  resolve against the SWEBOK reference / roadmap.sh manifest, and each role's
  `top_ka_codes` in roles.yaml must equal its `core`-level KAs.

## Question authoring checklist

Every question in `data/content/questions/role/role-discovery.yaml` must:

1. Measure exactly one **construct** (a dimension key), stated in the
   `construct` field and tagged `primary` in `agree_signals`.
2. Be a single-barreled, behavioral statement — one situation, one
   preference; no jargon a beginner cannot parse.
3. Declare `disagree_signals` naming what disagreement is evidence FOR
   (typically the `contrast` dimension) — disagreement is information, not
   absence of information.
4. Carry a `rationale` explaining why agreement indicates the construct.
5. Carry at least one `sources` reference (`swebok: {ka, topic}` or
   `roadmap_sh: {file, node}`) resolvable against the committed extracts.
6. Carry `review: {status: draft|reviewed, date}`.

## Review workflow (solo maintainer)

1. `manage.py validate_question_catalog --review-report` lists every cell and
   question still at `draft`.
2. For each item: read the rationale, check it against the cited source
   (SWEBOK reference YAML / roadmap.sh JSON node), fix the level or rationale
   if wrong, then flip `review.status` to `reviewed` with today's date.
3. If any **level** changed: run `manage.py generate_role_weights`, then the
   re-validation rule below, in the same commit.
4. Drafts never block seeding; `--strict-review` (exit 1 on any draft) is
   available for a content freeze once drafts reach zero.

## Re-validation rule (mandatory after ANY content change)

Any change to question signals, relevance levels, or the ladders must run:

```
manage.py simulate_personas --check-baseline data/simulation/persona_baseline.json
```

- The harness simulates noisy respondents for all 26 roles and reports top-1
  accuracy, precision-when-resolved, per-role accuracy, confusion pairs,
  tie-break utilization, and dead questions.
- Acceptance floor (full selection flow, 46 core + gated tie-breaks):
  top-1 ≥ 0.88, precision|resolved ≥ 0.99.
- If the change is intentional and metrics are acceptable, re-pin with
  `--write-baseline` and commit the baseline diff together with the content
  change, quoting the report in the commit message.
- The baseline stores the RNG seed and a digest of the question bank; the
  checker refuses to compare across different digests, so re-pinning is
  always an explicit, reviewable act.

## Known limitations (stated honestly)

- The persona harness measures **self-consistency** (personas are generated
  from the same profiles being scored), not human validity. It catches
  structural regressions, not badly-worded prompts.
- The initial relevance mapping was reverse-engineered from the previous
  hand-typed weights; cells remain `draft` until individually reviewed
  against sources. `review.status` is the boundary between "laundered" and
  "grounded".
- Real-respondent validation (item discrimination, test-retest reliability)
  requires pilot data that does not exist yet; the schema keeps per-item
  provenance so a future item-analysis can be joined against it.
