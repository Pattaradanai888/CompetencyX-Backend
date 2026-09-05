"""OpenAPI request/response examples for the assessments API."""

SESSION_CREATE_REQUEST_EXAMPLE = {
    'preferred_role_slug': 'backend-engineer',
    'language': 'en',
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
}

SESSION_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'status': 'in_progress',
    'phase': 'role_discovery',
    'language': 'en',
    'best_fit_confidence': 0.0,
    'preferred_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'name_th': 'นักพัฒนา Backend',
        'description': 'Builds APIs and backend services.',
        'description_th': 'สร้าง API และ service ฝั่ง backend',
    },
    'best_fit_role': None,
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
    'started_at': '2026-04-17T04:00:00Z',
    'updated_at': '2026-04-17T04:00:00Z',
    'completed_at': None,
    'milestones': {
        'answered_role_questions': 0,
        'answered_core_role_questions': 0,
        'answered_tie_break_questions': 0,
    },
    'role_alignment_status': 'unknown',
    'role_resolution_status': 'in_progress',
    'guidance_summary': 'You want to pursue Backend Engineer. Complete the role-discovery profile to compare fit.',
    'current_question': {
        'id': 101,
        'code': 'role-likert-build-working-parts',
        'stage': 'role',
        'question_type': 'likert_5',
        'prompt': 'I enjoy turning an idea into a working technical part.',
        'help_text': '',
        'role': None,
        'topic': None,
        'difficulty': 1,
        'options': [],
        'response_scale': [
            {
                'key': 'strongly_agree',
                'label': 'Strongly agree',
                'value': 2,
                'display_order': 1,
            },
            {
                'key': 'agree',
                'label': 'Agree',
                'value': 1,
                'display_order': 2,
            },
            {
                'key': 'neutral',
                'label': 'Neutral',
                'value': 0,
                'display_order': 3,
            },
            {
                'key': 'disagree',
                'label': 'Disagree',
                'value': -1,
                'display_order': 4,
            },
            {
                'key': 'strongly_disagree',
                'label': 'Strongly disagree',
                'value': -2,
                'display_order': 5,
            },
        ],
    },
}

# The Role Discovery endpoint serves exactly what the session payload carries in
# ``current_question``, so the example is that field rather than a second copy of it.
ROLE_DISCOVERY_NEXT_QUESTION_RESPONSE_EXAMPLE = {
    'next_question': SESSION_RESPONSE_EXAMPLE['current_question'],
}

ROLE_DISCOVERY_NEXT_QUESTION_EXHAUSTED_RESPONSE_EXAMPLE = {
    'next_question': None,
}

INSIGHTS_RESPONSE_EXAMPLE = {
    'role_resolution_status': 'resolved',
    'best_fit_role': {
        'id': 2,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'name_th': 'นักพัฒนา Backend',
        'description': 'Builds APIs, data flows, and server-side application logic.',
        'description_th': 'สร้าง API, data flow และ logic ของแอปพลิเคชันฝั่งเซิร์ฟเวอร์',
    },
    'best_fit_confidence': 0.71,
    'answered_role_questions': 3,
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'label_th': 'การออกแบบระบบ',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        },
        {
            'key': 'reliability_automation',
            'label': 'Reliability and Automation',
            'label_th': 'ความเชื่อถือได้และระบบอัตโนมัติ',
            'raw_score': 4.0,
            'normalized_score': 0.286,
            'evidence_count': 2,
        },
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'name_th': 'นักพัฒนา Backend',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
            'top_supporting_pillars_th': ['การออกแบบระบบ', 'ความเชื่อถือได้และระบบอัตโนมัติ', 'การใช้เหตุผลกับข้อมูล'],
        },
        {
            'slug': 'system-architect',
            'name': 'System Architect',
            'name_th': 'สถาปนิกระบบ',
            'fit_score': 0.58,
            'fit_share': 0.16,
            'top_supporting_pillars': ['Systems Design', 'Risk and Security'],
            'top_supporting_pillars_th': ['การออกแบบระบบ', 'ความเสี่ยงและความปลอดภัย'],
        },
    ],
    'guidance_summary': 'Your current answers align best with Backend Engineer.',
}

ANSWER_REQUEST_EXAMPLE = {
    'question_id': 101,
    'scale_value': 2,
    'response_time_ms': 4200,
    'confidence_indicator': 'high',
}

RESULT_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'status': 'completed',
    'phase': 'recommendation_ready',
    'best_fit_confidence': 0.8,
    'preferred_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'name_th': 'นักพัฒนา Backend',
        'description': 'Builds APIs and backend services.',
        'description_th': 'สร้าง API และ service ฝั่ง backend',
    },
    'best_fit_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'name_th': 'นักพัฒนา Backend',
        'description': 'Builds APIs and backend services.',
        'description_th': 'สร้าง API และ service ฝั่ง backend',
    },
    'profile': {
        'education_level': 'student',
        'current_stage': 'beginner',
    },
    'started_at': '2026-04-17T04:00:00Z',
    'updated_at': '2026-04-17T04:05:00Z',
    'completed_at': '2026-04-17T04:05:00Z',
    'milestones': {
        'answered_role_questions': 2,
        'answered_core_role_questions': 2,
        'answered_tie_break_questions': 0,
    },
    'role_alignment_status': 'aligned',
    'role_resolution_status': 'resolved',
    'guidance_summary': 'You are tracking well toward Backend Engineer.',
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'label_th': 'การออกแบบระบบ',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        }
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'name_th': 'นักพัฒนา Backend',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
            'top_supporting_pillars_th': ['การออกแบบระบบ', 'ความเชื่อถือได้และระบบอัตโนมัติ', 'การใช้เหตุผลกับข้อมูล'],
        }
    ],
}

HISTORY_RESPONSE_EXAMPLE = {
    'id': '2b39d41d-8de9-4b9b-b2ef-2a278b3f3770',
    'phase': 'recommendation_ready',
    'status': 'completed',
    'answers': [
        {
            'id': 401,
            'question_id': 101,
            'question_code': 'role-likert-build-working-parts',
            'question_prompt': 'I enjoy turning an idea into a working technical part.',
            'question_stage': 'role',
            'topic_slug': None,
            'selected_option_id': None,
            'selected_option_key': None,
            'selected_option_label': None,
            'scale_value': 2,
            'response_time_ms': 4200,
            'confidence_indicator': 'high',
            'responded_at': '2026-04-17T04:01:00Z',
        }
    ],
}

SKILL_ASSESSMENT_RESPONSE_EXAMPLE = {
    'completed': True,
    'answers': {
        'backend-developer--internet-and-web': 5,
        'backend-developer--databases': 2,
    },
    'completed_at': '2026-05-08T20:00:00Z',
    'topic_mastery': {'backend-developer--databases': 0.25},
    # Every entry carries its Canonical Thai Wording alongside the English, so
    # a Thai session reads Thai without rebuilding the sentence on the client.
    'topic_states': [
        {
            'topic_slug': 'backend-developer--databases',
            'topic_title': 'Data storage',
            'topic_title_th': 'การจัดเก็บข้อมูล',
            # The imported roadmap nodes the set covers, so a roadmap view can
            # mark them by slug.
            'node_slugs': ['databases', 'sql'],
            'state': 'assessed_gap',
            'mastery': 0.25,
        },
        {
            'topic_slug': 'backend-developer--caching',
            'topic_title': 'Caching',
            'topic_title_th': 'การแคช',
            'node_slugs': ['caching', 'redis'],
            'state': 'unassessed',
            'mastery': None,
        },
        {
            'topic_slug': 'backend-developer--internet-and-web',
            'topic_title': 'Internet and web protocols',
            'topic_title_th': 'อินเทอร์เน็ตและโปรโตคอลเว็บ',
            'node_slugs': ['internet', 'http'],
            'state': 'held',
            'mastery': 1.0,
            'statement': 'You said you can already work on "Internet and web protocols".',
            'statement_th': 'คุณระบุว่าคุณทำงานเรื่อง "อินเทอร์เน็ตและโปรโตคอลเว็บ" ได้แล้ว',
            # Held by a top self-rating, not by a mark: there is no mark to undo.
            'held_by_mark': False,
        },
    ],
    'recommended_topics': [
        {
            'topic_slug': 'backend-developer--databases',
            'topic_title': 'Data storage',
            'topic_title_th': 'การจัดเก็บข้อมูล',
            'node_slugs': ['databases', 'sql'],
            'state': 'assessed_gap',
            'mastery': 0.25,
            'reason': 'You rated "Data storage" low, and it builds on "Internet and web protocols".',
            'reason_th': 'คุณให้คะแนน "การจัดเก็บข้อมูล" ค่อนข้างต่ำ และหัวข้อนี้ต่อยอดจาก "อินเทอร์เน็ตและโปรโตคอลเว็บ"',
        },
        {
            'topic_slug': 'backend-developer--caching',
            'topic_title': 'Caching',
            'topic_title_th': 'การแคช',
            'node_slugs': ['caching', 'redis'],
            'state': 'unassessed',
            'mastery': None,
            'reason': 'The assessment has not asked about "Caching" yet.',
            'reason_th': 'แบบประเมินยังไม่ได้ถามเรื่อง "การแคช"',
        },
    ],
    'next_topics': [
        {
            'topic_slug': 'backend-developer--databases',
            'topic_title': 'Data storage',
            'topic_title_th': 'การจัดเก็บข้อมูล',
            'node_slugs': ['databases', 'sql'],
            'state': 'assessed_gap',
            'mastery': 0.25,
            'reason': 'You rated "Data storage" low, and it builds on "Internet and web protocols".',
            'reason_th': 'คุณให้คะแนน "การจัดเก็บข้อมูล" ค่อนข้างต่ำ และหัวข้อนี้ต่อยอดจาก "อินเทอร์เน็ตและโปรโตคอลเว็บ"',
        },
    ],
    'readiness': {
        'targets': {'backend-developer--databases': 0.6, 'backend-developer--caching': 0.6},
        'overall_target': 0.6,
        'overall_mastery': 0.25,
        'assessed_count': 1,
    },
    'progress': {
        'answered': 2,
        'total': 18,
        'remaining': 16,
        'floor': 12,
        'ceiling': 18,
        'settled': False,
    },
    'confidence': 'low',
}

# The answers a client proposes need not be saved yet: the stop rule reads
# only the answers handed in (ADR-0005).
SKILL_ASSESSMENT_NEXT_QUESTION_REQUEST_EXAMPLE = {
    'answers': {
        'backend-developer--internet-and-web': 5,
        'backend-developer--databases': 2,
    },
}

SKILL_ASSESSMENT_NEXT_QUESTION_RESPONSE_EXAMPLE = {
    'next_question': {
        'id': 'backend-developer--caching',
        'prompt': 'I could work on "Caching" in a real project without help.',
        'translations': {
            'en': {'prompt': 'I could work on "Caching" in a real project without help.'},
            'th': {'prompt': 'ฉันทำงานเรื่อง "การแคช" ในโปรเจกต์จริงได้เองโดยไม่ต้องมีคนช่วย'},
        },
        'dimension_key': 'backend-developer--caching',
        'display_order': 3,
        'topic_slug': 'backend-developer--caching',
        'topic_title': 'Caching',
    },
    'progress': {
        'answered': 2,
        'total': 18,
        'remaining': 16,
        'floor': 12,
        'ceiling': 18,
        'settled': False,
    },
}
