# 006 — Derive the readiness target from the role, not from a constant

**Label:** `ready-for-agent` · **Blocked by:** 005 · **Decided by:** [ADR-0002](../adr/0002-skill-assessment-measures-topic-self-placement.md)

## Summary

The "To-Be" figure the respondent is compared against is a hardcoded 78, applied flat to every dimension. The As-Is/To-Be spider chart — a headline element of the result page — therefore compares every respondent, on every role, to the same regular polygon. Derive the target from the role once ticket 005 gives readiness a role-anchored meaning.

## Verified evidence

- `const TARGET_READINESS_SCORE = 78` (`app/pages/roadmaps/[sessionId].vue:509`), passed to the overview as `:target-score` (line 957)
- The target polygon is that number on every axis: `value: props.targetScore / 100` mapped over all dimensions (`app/components/roadmaps/RoadmapCompletedOverview.vue:38-43`), fed to `SkillSpiderChart` as `target-dimensions` (line 252)
- The same constant drives `capabilityGap` and `isAtTarget` (`[sessionId].vue:511-517`), so "how far you are from ready" is distance from a constant
- The marketing example on the landing page uses the same pair of numbers ("Where you are 58% / Role target 78%"), so the constant reads as a real role target to a viewer

## Scope

- Replace the constant with a target derived from the role, expressed over the same axes the As-Is profile uses
- Update `capabilityGap` / `isAtTarget` to follow it
- Decide and document where the target lives: computed by the backend and served with the results (preferred — it is role content, not presentation), or derived client-side from data the API already returns
- Remove the constant rather than relocating it

## Acceptance criteria

- [ ] Two roles produce visibly different target profiles; a test asserts the target is not uniform across dimensions for at least one role
- [ ] The gap and the at-target flag are computed against the role's target
- [ ] A role lacking whatever the target derives from degrades to a stated, documented default instead of silently reintroducing a flat number
- [ ] `TARGET_READINESS_SCORE` no longer exists in the codebase
- [ ] Frontend tests and lint pass

## Out of scope

- Changing what the As-Is axes are — that follows from ticket 005
- Redesigning the spider chart component itself
