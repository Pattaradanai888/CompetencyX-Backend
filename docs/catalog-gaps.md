# Role-discovery question catalog gaps

Identified gaps in `data/content/questions/role/role-discovery.yaml` that limit
role-finding accuracy. These are content issues, not code issues — fixing them
requires writing new question YAML and re-seeding.

## 1. Specialization axis blind spot (13 dimensions with zero CORE coverage)

The entire role-specialization axis is absent from CORE questions. These roles
get **no scoring signal** during the main 36-question phase and rely entirely
on the 12 TIE_BREAK questions:

| Dimension                  | Affected roles                                      |
| -------------------------- | --------------------------------------------------- |
| `server_backend`             | backend-developer, full-stack, server-side-game      |
| `android_platform`           | android-developer                                    |
| `ios_platform`              | ios-developer                                       |
| `database_postgresql`        | postgresql-developer-dba                            |
| `blockchain_platform`        | blockchain-developer                                |
| `game_client`               | game-developer                                      |
| `game_server`                | server-side-game-developer                          |
| `game_family`                | game-developer, server-side-game-developer         |
| `technical_documentation`     | technical-writer, developer-relations              |
| `business_intelligence`       | bi-analyst                                          |
| `ml_platform`                | machine-learning-engineer, mlops-engineer          |
| `developer_community` (1 Q only) | developer-relations                              |

**Impact:** 11 of 26 roles are effectively invisible until TIE_BREAK. Adding
CORE questions for these dimensions is the single biggest improvement lever
for role coverage and resolution speed.

## 2. Agree-only dimensions (upward bias)

These dimensions never appear as a `disagree_dimension_signals` target, so
they only accumulate positive evidence and never get suppressed:

`quality`, `testing`, `security`, `math`, `maintenance`,
`configuration_management`, `models_methods`, `data_ai`,
`documentation_practice`

**Impact:** Roles weighted heavily on these dimensions (e.g., qa-engineer on
`quality`/`testing`, cyber-security on `security`) get artificially inflated
scores when users give non-committal answers.

## 3. `construction` over-representation

`construction` appears in **14 of 36 CORE questions** (39%), mostly as the
universal disagree foil. This over-weights construction in the evidence and
dilutes its discriminative value.

**Fix:** Diversify disagree targets across questions. Use the role-family
dimensions (`backend_platform`, `application_build`, etc.) as alternative
foils.
