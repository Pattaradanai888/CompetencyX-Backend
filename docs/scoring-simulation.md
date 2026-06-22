# Scoring simulation & tuning

Fast, drift-proof tooling for experimenting with the role-discovery scoring
algorithm in `assessments/scoring.py`.

## Architecture

All scoring math lives in **`assessments/scoring.py`** — a pure-Python module
with no Django imports. It is the single source of truth shared by:

- **Production** (`assessments/role_inference.py`) — loads Django rows, hands
  plain dicts to `scoring.*`, writes results back to the session.
- **In-memory simulator** (`simulation/engine.py`) — runs synthetic
  sessions entirely in Python, never touching the database.

Because both paths call the same functions, simulation results cannot drift
from production. The test `assessments/tests.py::ScoringParityTests` locks
this: it seeds the catalog, answers questions through the real DB flow, and
asserts the pure path produces an identical snapshot.

> **Rule:** if you change scoring math, change it in `scoring.py` only.
> Both production and the simulator pick it up automatically.

## Commands

### `simulate_inmemory` — fast Monte Carlo simulation

Runs N synthetic role-discovery sessions in parallel via
`ProcessPoolExecutor`. No database writes.

```bash
# 1000 sessions with the default uniform Likert distribution
python manage.py simulate_inmemory --samples 1000

# Realistic centered distribution (more neutral answers)
python manage.py simulate_inmemory --samples 5000 --likert-weights 0.1,0.2,0.4,0.2,0.1

# JSON output for piping into a notebook
python manage.py simulate_inmemory --samples 2000 --format json > run.json

# Fix the first few answers to probe a specific scenario
python manage.py simulate_inmemory --samples 500 --prefix-answers 2,2,-1,1
```

Default `--likert-weights` is uniform (`0.2,0.2,0.2,0.2,0.2`) to match the
DB-backed `simulate_assessment` command; use `0.1,0.2,0.4,0.2,0.1` for a
realistic distribution centered on "neutral".

**Speed:** ~1000 samples in ~7s (vs ~2.2s **per sample** for the DB-backed
`simulate_assessment`). That is roughly **300x** faster per sample.

### `tune_scoring` — hyperparameter grid search

Runs the cartesian product of scoring constants from a YAML grid, keeping
the Monte Carlo answer stream identical across trials so the only variable
is the parameters.

```bash
python manage.py tune_scoring --grid data/scoring_tuning_grid.yaml --samples 500
```

Rank by an alternative metric:

```bash
python manage.py tune_scoring --grid data/scoring_tuning_grid.yaml \
    --samples 1000 --metric resolved_role_coverage_rate
```

Available metrics: `resolved_rate`, `low_confidence_rate`,
`resolved_role_coverage_rate`, `resolved_uniformity`, `ambiguous_rate`.

The grid file format:

```yaml
grid:
  ROLE_SCORE_SOFTMAX_TEMPERATURE: [1.5, 2.0, 2.242, 2.5, 3.0]
  ROLE_DISCOVERY_CONFIDENCE_THRESHOLD: [0.25, 0.289, 0.33]
  ROLE_EVIDENCE_SCORE_SCALE: [4.0, 5.229, 6.0]
```

Tunable constants are listed in `simulation/engine.py::TUNABLE_PARAM_NAMES`.

### `simulate_assessment` — DB-backed simulation (slow, real flow)

The original DB-backed simulator. Still useful when you need to exercise the
full Django stack (signals, recommendations, transactions). See
`assessments/management/commands/simulate_assessment.py`.

## Reproducibility

Both commands accept `--random-seed` (default `42`). The simulator
pre-generates the full answer stream in the parent process from the seed, so
results are reproducible regardless of worker scheduling.

## Verifying parity

```bash
# Single-sample smoke probe from the in-memory command
python manage.py simulate_inmemory --parity-check

# Run the parity test suite
uv run pytest assessments/tests.py::ScoringParityTests -v
```
