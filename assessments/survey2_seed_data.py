SURVEY2_DIMENSIONS = [
    {
        'dimension_key': 'psp-planning',
        'label': 'PSP Planning',
        'track': 'psp',
        'low_score_action': 'Use a small planning log for the next 3 tasks: estimated time, actual time, variance, and one cause of delay.',
        'display_order': 1,
    },
    {
        'dimension_key': 'psp-quality',
        'label': 'PSP Quality Discipline',
        'track': 'psp',
        'low_score_action': 'Create a personal review checklist and record defects found before submitting work.',
        'display_order': 2,
    },
    {
        'dimension_key': 'sdlc-requirements',
        'label': 'Requirements Analysis',
        'track': 'sdlc',
        'low_score_action': 'Practice converting one feature idea into user need, acceptance criteria, constraints, and open questions.',
        'display_order': 3,
    },
    {
        'dimension_key': 'sdlc-design',
        'label': 'System Design & Architecture',
        'track': 'sdlc',
        'low_score_action': 'Sketch components, data flow, and two tradeoffs before implementation.',
        'display_order': 4,
    },
    {
        'dimension_key': 'sdlc-development',
        'label': 'Development / Coding',
        'track': 'sdlc',
        'low_score_action': 'Implement a small feature following existing project conventions, then refactor one part for readability.',
        'display_order': 5,
    },
    {
        'dimension_key': 'sdlc-testing',
        'label': 'Testing & QA',
        'track': 'sdlc',
        'low_score_action': 'Write one normal-case test and two edge-case checks for the next feature you build.',
        'display_order': 6,
    },
    {
        'dimension_key': 'sdlc-deployment',
        'label': 'Deployment & Release',
        'track': 'sdlc',
        'low_score_action': 'Document a release checklist: build, configuration, migration, smoke test, rollback, and owner.',
        'display_order': 7,
    },
    {
        'dimension_key': 'sdlc-maintenance',
        'label': 'Maintenance & Support',
        'track': 'sdlc',
        'low_score_action': 'Trace one existing bug from report to root cause, fix plan, regression check, and release note.',
        'display_order': 8,
    },
]

SURVEY2_QUESTIONS = [
    {
        'question_id': 'psp-plan-estimate',
        'prompt': 'Before building a web feature, I estimate effort, complexity, and delivery time using a repeatable method.',
        'dimension_key': 'psp-planning',
        'display_order': 1,
    },
    {
        'question_id': 'psp-plan-compare',
        'prompt': 'After implementation, I compare actual vs estimated time and document why variances happened.',
        'dimension_key': 'psp-planning',
        'display_order': 2,
    },
    {
        'question_id': 'psp-quality-defects',
        'prompt': 'I track defects by type (logic, integration, validation, UI) and use that data to prevent repeat issues.',
        'dimension_key': 'psp-quality',
        'display_order': 3,
    },
    {
        'question_id': 'psp-quality-review',
        'prompt': 'Before merge or release, I run a personal quality checklist (tests, edge cases, readability, security basics).',
        'dimension_key': 'psp-quality',
        'display_order': 4,
    },
    {
        'question_id': 'sdlc-req-criteria',
        'prompt': 'I can turn a product request into clear web-ready acceptance criteria, constraints, and unresolved questions.',
        'dimension_key': 'sdlc-requirements',
        'display_order': 5,
    },
    {
        'question_id': 'sdlc-design-tradeoffs',
        'prompt': 'Before coding, I can map UI/API/data flow and explain tradeoffs (speed, maintainability, scalability).',
        'dimension_key': 'sdlc-design',
        'display_order': 6,
    },
    {
        'question_id': 'sdlc-dev-conventions',
        'prompt': 'I can implement maintainable web code that follows project architecture, naming, and review standards.',
        'dimension_key': 'sdlc-development',
        'display_order': 7,
    },
    {
        'question_id': 'sdlc-test-strategy',
        'prompt': 'I define tests for happy path, edge cases, and regression risk before shipping a feature.',
        'dimension_key': 'sdlc-testing',
        'display_order': 8,
    },
    {
        'question_id': 'sdlc-release-checklist',
        'prompt': 'I can execute a safe web release plan including environment checks, migrations, smoke tests, and rollback.',
        'dimension_key': 'sdlc-deployment',
        'display_order': 9,
    },
    {
        'question_id': 'sdlc-maintain-debug',
        'prompt': 'I can debug production-like web issues, ship fixes safely, and avoid unrelated regressions.',
        'dimension_key': 'sdlc-maintenance',
        'display_order': 10,
    },
    {
        'question_id': 'sdlc-collab-blockers',
        'prompt': 'During delivery, I communicate blockers, assumptions, and decision changes early enough for team action.',
        'dimension_key': 'sdlc-maintenance',
        'display_order': 11,
    },
]

SURVEY2_ROLE_GUIDANCE = {
    None: [
        'Use the lowest Survey 2 dimensions as execution habits to practice while working through the recommended roadmap topics.',
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
    'software-architect': [
        'Prioritize architecture tradeoffs, quality attributes, technical risk, documentation, and evolutionary design.',
        'For each roadmap topic, document context, constraints, alternatives, decision, and expected quality impact.',
    ],
}
