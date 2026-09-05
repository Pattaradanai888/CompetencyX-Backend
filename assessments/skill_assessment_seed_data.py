"""Authored Skill Assessment guidance, one short list per role.

The PSP/SDLC dimensions and items that used to be seeded here were retired
once every role had authored Assessable Topic Sets (ADR-0005); the items are
now generated from those sets. Only the per-role guidance is authored content.
"""

SKILL_ASSESSMENT_ROLE_GUIDANCE = {
    None: [
        'Use the lowest Skill Assessment dimensions as execution habits to practice while working through the recommended roadmap topics.',
        'For each topic, create one small artifact that proves progress: plan, checklist, test, design note, or reflection.',
    ],
    'backend-developer': [
        'Prioritize API contracts, data modeling, automated tests, deployment checks, and production debugging practice.',
        'For each roadmap topic, produce a small backend artifact: endpoint design, schema change, test case, and release note.',
    ],
    'qa-engineer': [
        'Prioritize test design, defect classification, regression strategy, automation, and release quality gates.',
        'For each roadmap topic, produce test cases, risk notes, and a defect-prevention checklist.',
    ],
    'devops-engineer': [
        'Prioritize release planning, CI/CD safety, monitoring, incident response, and operational feedback loops.',
        'For each roadmap topic, document pipeline steps, environment assumptions, rollback strategy, and observability checks.',
    ],
    'devsecops-engineer': [
        'Prioritize secure release gates, threat modeling, vulnerability handling, and security regression checks.',
        'For each roadmap topic, add a security risk note and one verification step to the release checklist.',
    ],
    'product-manager': [
        'Prioritize requirements discovery, acceptance criteria, stakeholder alignment, prioritization, and delivery feedback.',
        'For each roadmap topic, define user value, success metric, risk, and acceptance criteria.',
    ],
    'frontend-developer': [
        'Prioritize component structure, state management, accessibility, responsive behavior, and browser performance.',
        'For each roadmap topic, ship a small interface: a component, its states, an accessibility check, and a rendering-cost note.',
    ],
    'full-stack-developer': [
        'Prioritize moving a feature end to end: data model, API contract, interface, and the seam between them.',
        'For each roadmap topic, deliver one thin vertical slice and note where the frontend and backend assumptions had to agree.',
    ],
    'android-developer': [
        'Prioritize activity and lifecycle handling, state restoration, background work, and behavior on constrained devices.',
        'For each roadmap topic, build a screen or service and record how it behaves across rotation, process death, and poor connectivity.',
    ],
    'ios-developer': [
        'Prioritize view composition, state and navigation, memory behavior, and platform conventions.',
        'For each roadmap topic, build a screen and note the lifecycle events, retain cycles, and human-interface conventions it touches.',
    ],
    'data-analyst': [
        'Prioritize question framing, data cleaning, analysis you can defend, and presenting a finding a decision can rest on.',
        'For each roadmap topic, produce one analysis with its assumptions, its caveats, and the decision it supports.',
    ],
    'bi-analyst': [
        'Prioritize metric definitions, dimensional modeling, dashboard readability, and knowing which number answers which question.',
        'For each roadmap topic, publish one dashboard element with a written metric definition and its refresh and ownership notes.',
    ],
    'data-engineer': [
        'Prioritize pipeline reliability, schema evolution, data quality checks, and recovering from a bad run.',
        'For each roadmap topic, build a pipeline step with its idempotency argument, a data quality assertion, and a backfill plan.',
    ],
    'ai-data-scientist': [
        'Prioritize problem framing, feature reasoning, honest evaluation, and knowing when a model is not the answer.',
        'For each roadmap topic, produce an experiment with a baseline, an evaluation protocol, and a written limitation.',
    ],
    'ai-engineer': [
        'Prioritize integrating models into real systems: prompt and context design, evaluation, latency and cost, and failure handling.',
        'For each roadmap topic, ship a feature with an evaluation set, a fallback path, and a measured cost per request.',
    ],
    'machine-learning-engineer': [
        'Prioritize training reproducibility, feature pipelines, evaluation that matches production, and serving behavior.',
        'For each roadmap topic, produce a reproducible run with its data version, metrics, and a note on training and serving skew.',
    ],
    'mlops-engineer': [
        'Prioritize model deployment, monitoring for drift, rollback, and the governance trail behind a released model.',
        'For each roadmap topic, document the pipeline step, its monitoring signal, its rollback path, and what gets recorded.',
    ],
    'cyber-security-engineer-analyst': [
        'Prioritize threat modeling, control verification, detection, and responding to an incident with evidence.',
        'For each roadmap topic, write a threat and its control, then verify the control and record the evidence.',
    ],
    'blockchain-developer': [
        'Prioritize contract correctness, gas and cost behavior, key handling, and the fact that a deployed mistake is permanent.',
        'For each roadmap topic, deliver a contract or integration with its tests, its failure modes, and its upgrade or exit path.',
    ],
    'postgresql-developer-dba': [
        'Prioritize schema design, query plans, index strategy, locking behavior, and safe change under load.',
        'For each roadmap topic, produce a schema or query change with its plan before and after, and its migration safety note.',
    ],
    'game-developer': [
        'Prioritize the game loop, input feel, physics and collision behavior, and holding a frame budget.',
        'For each roadmap topic, build a playable slice and record its frame cost and one tuning decision about how it feels.',
    ],
    'server-side-game-developer': [
        'Prioritize authoritative state, latency compensation, matchmaking, persistence, and behavior under a live spike.',
        'For each roadmap topic, build a service and note its authority model, its tick or update budget, and its failure behavior.',
    ],
    'ux-designer': [
        'Prioritize user research, interaction flows, prototyping, and validating a design against real behavior rather than taste.',
        'For each roadmap topic, produce a flow or prototype with the question it tests and what you learned from testing it.',
    ],
    'technical-writer': [
        'Prioritize audience and task analysis, structure, accuracy against the running system, and maintaining what you publish.',
        'For each roadmap topic, publish one document with its intended reader, the task it completes, and how it is kept current.',
    ],
    'developer-relations': [
        'Prioritize teaching a concept clearly, working demos, gathering developer feedback, and carrying it back to the product.',
        'For each roadmap topic, produce a demo or explainer and record one concrete piece of feedback it surfaced.',
    ],
    'engineering-manager': [
        'Prioritize delivery predictability, technical health, feedback and growth for people, and decisions that survive scrutiny.',
        'For each roadmap topic, document the decision, who it affects, how it is measured, and what would make you reverse it.',
    ],
    'software-architect': [
        'Prioritize architecture tradeoffs, quality attributes, technical risk, documentation, and evolutionary design.',
        'For each roadmap topic, document context, constraints, alternatives, decision, and expected quality impact.',
    ],
}
