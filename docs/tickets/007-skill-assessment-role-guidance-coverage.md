# 007 — Close the Skill Assessment role guidance gap

**Label:** `ready-for-agent` · **Blocked by:** 005 · **Decided by:** [ADR-0002](../adr/0002-skill-assessment-measures-topic-self-placement.md)

## Summary

Skill Assessment guidance is written for 6 of 26 roles. The other 20 silently fall back to generic text, so most respondents receive advice that names nothing specific to the role they chose.

## Verified evidence

- 14 guidance rows covering 6 roles: `backend-developer`, `devops-engineer`, `devsecops-engineer`, `product-manager`, `qa-engineer`, `software-architect` (`assessments/skill_assessment_seed_data.py:224+`)
- The other 20 active roles have none, including `mlops-engineer`, `frontend-developer`, `ai-engineer`, `ux-designer`, `data-analyst`
- The fallback is silent: `list_skill_assessment_role_guidance` returns role rows when present, otherwise the rows with `role IS NULL` (`assessments/services/skill_assessment_service.py:75-88`). Nothing surfaces that a respondent is seeing generic text
- Reproduced end to end on 2026-08-18: a session that resolved to MLOps Engineer was given the generic guidance

## Scope

- Guidance for the 20 uncovered roles, written against the instrument ticket 005 introduces (topic-anchored), not the retired PSP/SDLC dimensions
- A check that fails when an active role has no guidance, so the gap cannot silently reopen as roles are added
- Decide whether the generic fallback stays at all, or whether missing guidance should be visible rather than papered over

## Acceptance criteria

- [ ] Every active role has guidance, or the absence is explicit in the response rather than substituted
- [ ] A test asserts guidance coverage over active roles
- [ ] Thai translations present wherever the existing guidance rows carry them
- [ ] `.venv\Scripts\python.exe -m pytest -n auto` and `.venv\Scripts\python.exe -m ruff check .` pass

## Out of scope

- The instrument itself (ticket 005)
- Rewriting the six existing roles' guidance beyond what ticket 005's change of instrument requires
