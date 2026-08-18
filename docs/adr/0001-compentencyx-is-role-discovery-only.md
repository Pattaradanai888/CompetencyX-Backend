# CompentencyX is a Role Discovery product only — enterprise competency is out of scope

**Status:** Accepted

## Context

A specific organization wants an enterprise competency-management system: track employees, record training, measure attained competencies, and map those to career path, promotion, and salary. A working FastAPI prototype already implements most of that competency-tracking engine — the **CoachCall** project (a separate repo at `D:\Flook\SE\Senior Project\CoachCall-Backend`), whose model (Skill / Task / TaskSkillWeight / TaskCompletion / AthleteSkill / ExperienceLevel / Position) maps directly onto the enterprise need. The question arose whether to build or convert that system inside CompentencyX.

## Decision

CompentencyX remains solely a **Role Discovery** product — helping individuals (the Primary Role Discovery Respondent) explore plausible technology career directions and understand the evidence behind each one. Enterprise competency management is **out of scope** for this repository.

## Why

Role Discovery and enterprise competency are different bounded contexts with non-overlapping ubiquitous languages and no shared user flow. The stakeholder explicitly scoped them as independent ("ทำใหม่ ไม่เชื่อม" — build fresh, don't connect). Co-locating a second, unrelated context here would create a two-headed product whose two halves share nothing but a project shell and a database, while introducing real term collisions in code (`Session`, `Role`, `Skill` mean different things in each). On top of that, the competency engine already exists and works in CoachCall; rebuilding it in Django here would discard working code for no functional gain.

## Considered Options

- **(Chosen) Keep CompentencyX as Role Discovery only; enterprise competency lives elsewhere.** The competency product is built by extending CoachCall, not by touching this repo.
- **Pivot this repo to enterprise competency.** Rejected — it throws away the Role Discovery product *and* still requires rebuilding the competency engine that CoachCall already has.
- **Add enterprise competency as a second bounded context in this repo.** Rejected — the two contexts are deliberately unconnected, so co-locating them yields only collisions (`AssessmentSession` vs training session; `Role` candidate vs job title; Skill Assessment vs competency) and a split codebase with no shared benefit.

## Consequences

- `CONTEXT.md` stays a single-context Role Discovery glossary. Do **not** add Organization / Employee / Competency / Training / Career-Path terms here — they belong to the CoachCall/enterprise context.
- Enterprise competency work happens in the CoachCall project, not here.
- A future request to "add HR / competency / employee tracking" to CompentencyX should be redirected to the enterprise context per this ADR, unless this decision is deliberately revisited (and this ADR superseded).
