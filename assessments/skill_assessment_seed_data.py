SKILL_ASSESSMENT_DIMENSIONS = [
    {
        'dimension_key': 'psp-planning',
        'label': 'PSP Planning',
        'track': 'psp',
        'low_score_action': 'Use a small planning log for the next 3 tasks: estimated time, actual time, variance, and one cause of delay.',
        'translations': {
            'th': {
                'low_score_action': 'ลองใช้สมุดบันทึกวางแผนง่าย ๆ สำหรับ 3 งานถัดไป: เวลาที่ประมาณไว้ เวลาจริง ค่าความต่าง และสาเหตุของความล่าช้าอย่างน้อยหนึ่งสาเหตุ',
            },
        },
        'display_order': 1,
    },
    {
        'dimension_key': 'psp-quality',
        'label': 'PSP Quality Discipline',
        'track': 'psp',
        'low_score_action': 'Create a personal review checklist and record defects found before submitting work.',
        'translations': {
            'th': {
                'low_score_action': 'สร้าง checklist ทบทวนงานส่วนตัวและบันทึกข้อบกพร่องที่พบก่อนส่งงานทุกครั้ง',
            },
        },
        'display_order': 2,
    },
    {
        'dimension_key': 'sdlc-requirements',
        'label': 'Requirements Analysis',
        'track': 'sdlc',
        'low_score_action': 'Practice converting one feature idea into user need, acceptance criteria, constraints, and open questions.',
        'translations': {
            'th': {
                'low_score_action': 'ฝึกเปลี่ยนแนวคิดฟีเจอร์หนึ่งอย่างเป็นความต้องการผู้ใช้ เกณฑ์การยอมรับ ข้อจำกัด และคำถามที่ยังไม่มีคำตอบ',
            },
        },
        'display_order': 3,
    },
    {
        'dimension_key': 'sdlc-design',
        'label': 'System Design & Architecture',
        'track': 'sdlc',
        'low_score_action': 'Sketch components, data flow, and two tradeoffs before implementation.',
        'translations': {
            'th': {
                'low_score_action': 'วาดส่วนประกอบ data flow และข้อแลกเปลี่ยนสองข้อก่อนเริ่มลงมือเขียนโค้ด',
            },
        },
        'display_order': 4,
    },
    {
        'dimension_key': 'sdlc-development',
        'label': 'Development / Coding',
        'track': 'sdlc',
        'low_score_action': 'Implement a small feature following existing project conventions, then refactor one part for readability.',
        'translations': {
            'th': {
                'low_score_action': 'พัฒนาฟีเจอร์เล็ก ๆ ตาม convention ของโปรเจกต์ จากนั้น refactor ส่วนใดส่วนหนึ่งให้อ่านง่ายขึ้น',
            },
        },
        'display_order': 5,
    },
    {
        'dimension_key': 'sdlc-testing',
        'label': 'Testing & QA',
        'track': 'sdlc',
        'low_score_action': 'Write one normal-case test and two edge-case checks for the next feature you build.',
        'translations': {
            'th': {
                'low_score_action': 'เขียน test สำหรับกรณีปกติหนึ่งกรณีและทดสอบ edge case อีกสองกรณี สำหรับฟีเจอร์ถัดไปที่คุณสร้าง',
            },
        },
        'display_order': 6,
    },
    {
        'dimension_key': 'sdlc-deployment',
        'label': 'Deployment & Release',
        'track': 'sdlc',
        'low_score_action': 'Document a release checklist: build, configuration, migration, smoke test, rollback, and owner.',
        'translations': {
            'th': {
                'low_score_action': 'จัดทำ release checklist: build, configuration, migration, smoke test, rollback และผู้รับผิดชอบ',
            },
        },
        'display_order': 7,
    },
    {
        'dimension_key': 'sdlc-maintenance',
        'label': 'Maintenance & Support',
        'track': 'sdlc',
        'low_score_action': 'Trace one existing bug from report to root cause, fix plan, regression check, and release note.',
        'translations': {
            'th': {
                'low_score_action': 'ตามรอยบั๊กที่มีอยู่ตั้งแต่รายงานจนถึงสาเหตุที่แท้จริง วางแผนแก้ไข ตรวจสอบ regression และเขียน release note',
            },
        },
        'display_order': 8,
    },
]

SKILL_ASSESSMENT_QUESTIONS = [
    {
        'question_id': 'psp-plan-estimate',
        'prompt': 'Before building a web feature, I estimate effort, complexity, and delivery time using a repeatable method.',
        'translations': {
            'th': {
                'prompt': 'ก่อนสร้างฟีเจอร์เว็บ ฉันประเมินแรงงาน ความซับซ้อน และเวลาส่งมอบด้วยวิธีที่ทำซ้ำได้',
            },
        },
        'dimension_key': 'psp-planning',
        'display_order': 1,
    },
    {
        'question_id': 'psp-plan-compare',
        'prompt': 'After implementation, I compare actual vs estimated time and document why variances happened.',
        'translations': {
            'th': {
                'prompt': 'หลังพัฒนาเสร็จ ฉันเปรียบเทียบเวลาจริงกับเวลาที่ประเมินไว้ และบันทึกสาเหตุของความคลาดเคลื่อน',
            },
        },
        'dimension_key': 'psp-planning',
        'display_order': 2,
    },
    {
        'question_id': 'psp-quality-defects',
        'prompt': 'I track defects by type (logic, integration, validation, UI) and use that data to prevent repeat issues.',
        'translations': {
            'th': {
                'prompt': 'ฉันติดตามข้อบกพร่องตามประเภท เช่น ตรรกะ การเชื่อมต่อ การตรวจสอบข้อมูล และ UI แล้วใช้ข้อมูลนั้นป้องกันปัญหาซ้ำ',
            },
        },
        'dimension_key': 'psp-quality',
        'display_order': 3,
    },
    {
        'question_id': 'psp-quality-review',
        'prompt': 'Before merge or release, I run a personal quality checklist (tests, edge cases, readability, security basics).',
        'translations': {
            'th': {
                'prompt': 'ก่อน merge หรือ release ฉันใช้ checklist คุณภาพส่วนตัว เช่น test, edge case, ความอ่านง่าย และพื้นฐานความปลอดภัย',
            },
        },
        'dimension_key': 'psp-quality',
        'display_order': 4,
    },
    {
        'question_id': 'sdlc-req-criteria',
        'prompt': 'I can turn a product request into clear web-ready acceptance criteria, constraints, and unresolved questions.',
        'translations': {
            'th': {
                'prompt': 'ฉันสามารถเปลี่ยนคำขอของผลิตภัณฑ์ให้เป็น acceptance criteria ข้อจำกัด และคำถามค้างคาที่พร้อมใช้กับงานเว็บได้อย่างชัดเจน',
            },
        },
        'dimension_key': 'sdlc-requirements',
        'display_order': 5,
    },
    {
        'question_id': 'sdlc-design-tradeoffs',
        'prompt': 'Before coding, I can map UI/API/data flow and explain tradeoffs (speed, maintainability, scalability).',
        'translations': {
            'th': {
                'prompt': 'ก่อนเขียนโค้ด ฉันสามารถวางผัง UI, API, data flow และอธิบาย tradeoff ด้านความเร็ว การดูแลรักษา และการขยายระบบได้',
            },
        },
        'dimension_key': 'sdlc-design',
        'display_order': 6,
    },
    {
        'question_id': 'sdlc-dev-conventions',
        'prompt': 'I can implement maintainable web code that follows project architecture, naming, and review standards.',
        'translations': {
            'th': {
                'prompt': 'ฉันสามารถพัฒนาโค้ดเว็บที่ดูแลรักษาง่าย และทำตามสถาปัตยกรรม การตั้งชื่อ และมาตรฐานการ review ของโปรเจกต์',
            },
        },
        'dimension_key': 'sdlc-development',
        'display_order': 7,
    },
    {
        'question_id': 'sdlc-test-strategy',
        'prompt': 'I define tests for happy path, edge cases, and regression risk before shipping a feature.',
        'translations': {
            'th': {
                'prompt': 'ฉันกำหนด test สำหรับ happy path, edge case และความเสี่ยง regression ก่อนส่งมอบฟีเจอร์',
            },
        },
        'dimension_key': 'sdlc-testing',
        'display_order': 8,
    },
    {
        'question_id': 'sdlc-release-checklist',
        'prompt': 'I can execute a safe web release plan including environment checks, migrations, smoke tests, and rollback.',
        'translations': {
            'th': {
                'prompt': 'ฉันสามารถดำเนินแผน release เว็บอย่างปลอดภัย รวมถึงตรวจ environment, migration, smoke test และ rollback',
            },
        },
        'dimension_key': 'sdlc-deployment',
        'display_order': 9,
    },
    {
        'question_id': 'sdlc-maintain-debug',
        'prompt': 'I can debug production-like web issues, ship fixes safely, and avoid unrelated regressions.',
        'translations': {
            'th': {
                'prompt': 'ฉันสามารถ debug ปัญหาเว็บที่คล้าย production, ส่ง fix อย่างปลอดภัย และหลีกเลี่ยง regression ที่ไม่เกี่ยวข้อง',
            },
        },
        'dimension_key': 'sdlc-maintenance',
        'display_order': 10,
    },
    {
        'question_id': 'sdlc-collab-blockers',
        'prompt': 'During delivery, I communicate blockers, assumptions, and decision changes early enough for team action.',
        'translations': {
            'th': {
                'prompt': 'ระหว่างการส่งมอบงาน ฉันสื่อสาร blocker, assumption และการเปลี่ยนแปลงการตัดสินใจเร็วพอให้ทีมลงมือได้ทัน',
            },
        },
        'dimension_key': 'sdlc-maintenance',
        'display_order': 11,
    },
]

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
    'software-architect': [
        'Prioritize architecture tradeoffs, quality attributes, technical risk, documentation, and evolutionary design.',
        'For each roadmap topic, document context, constraints, alternatives, decision, and expected quality impact.',
    ],
}
