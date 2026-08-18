# 003 — Make recommendations deterministic + restore prerequisite gating

**Label:** `ready-for-agent` · **Blocked by:** none

## Summary

Two verified engine defects make `results` unstable and recommendations sparse:

1. **Non-determinism**: `_select_q_learning_topic` uses unseeded `random.random()` / `random.choice()` (`assessments/services/recommendation_service.py:243-244`) and re-runs on every answer once `RECOMMENDATION_READY` — same session state can produce a different recommended topic on every GET/answer.
2. **Prerequisite gating rot**: after the skill-stage removal, mastery no longer exists, so `_get_eligible_recommendation_topics` only admits topics whose prerequisites all have `required_mastery_threshold <= 0.0` (`recommendation_service.py:102-108`) — any topic gated by a real prerequisite is unreachable. Under Q-learning the projected-eligibility path has the same rot (`recommendation_service.py:316-322`).

## Verified evidence

- `random` module used at `recommendation_service.py:2,243-244`, no seeding anywhere
- `recompute_mastery` / `TopicMastery` references removed from assessments services; `session.mastery_scores` no longer populated
- Default policy is `q_learning` (`config/settings/base.py:126`)

## Decisions to make inside this ticket (pick deliberately, record in PR)

- **Determinism**: seed an `random.Random` instance per session (e.g. from `session.id`) — reproducible, keeps exploration. (Alternative: drop ε-greedy in production; rejected for now, keep behavior stable.)
- **Gating**: choose one and state it in the PR —
  (a) treat prerequisites with no mastery source as satisfied (roadmap order still respected via `display_order`), or
  (b) disable prerequisite gating until a mastery source returns.
  Both restore gated topics to eligibility; (a) is the recommended minimal semantic.

## Acceptance criteria

- [ ] Same session state → same recommended topic across repeated calls (test: call `refresh_recommendations` twice, assert identical output)
- [ ] Topics with real prerequisites are eligible again (test with seeded topic graph)
- [ ] The chosen gating semantic is documented in the PR description and reflected in `reason` text
- [ ] `uv run pytest -n auto` and `uv run ruff check .` pass
