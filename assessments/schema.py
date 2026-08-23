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
        'description': 'Builds APIs and backend services.',
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

INSIGHTS_RESPONSE_EXAMPLE = {
    'role_resolution_status': 'resolved',
    'best_fit_role': {
        'id': 2,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs, data flows, and server-side application logic.',
    },
    'best_fit_confidence': 0.71,
    'answered_role_questions': 3,
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        },
        {
            'key': 'reliability_automation',
            'label': 'Reliability and Automation',
            'raw_score': 4.0,
            'normalized_score': 0.286,
            'evidence_count': 2,
        },
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
        },
        {
            'slug': 'system-architect',
            'name': 'System Architect',
            'fit_score': 0.58,
            'fit_share': 0.16,
            'top_supporting_pillars': ['Systems Design', 'Risk and Security'],
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
        'description': 'Builds APIs and backend services.',
    },
    'best_fit_role': {
        'id': 1,
        'slug': 'backend-engineer',
        'name': 'Backend Engineer',
        'description': 'Builds APIs and backend services.',
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
    'guidance_summary': 'You are tracking well toward Backend Engineer. Focus next on Databases, HTTP Fundamentals.',
    'pillar_profile': [
        {
            'key': 'systems_design',
            'label': 'Systems Design',
            'raw_score': 7.0,
            'normalized_score': 0.5,
            'evidence_count': 3,
        }
    ],
    'ranked_roles': [
        {
            'slug': 'backend-engineer',
            'name': 'Backend Engineer',
            'fit_score': 0.71,
            'fit_share': 0.18,
            'top_supporting_pillars': ['Systems Design', 'Reliability and Automation', 'Data Reasoning'],
        }
    ],
    'preferred_role_gap_topics': [
        {
            'id': 12,
            'slug': 'databases',
            'title': 'Databases',
            'description': 'Relational data modeling and SQL.',
            'difficulty': 'beginner',
            'display_order': 2,
            'parent_id': None,
            'prerequisites': [
                {
                    'topic_id': 11,
                    'required_mastery_threshold': 0.7,
                    'dependency_weight': 1.0,
                }
            ],
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
        'q-req': 4,
        'q-design': 5,
        'q-dev': 4,
        'q-test': 3,
        'q-release': 3,
        'q-psp': 4,
    },
    'completed_at': '2026-05-08T20:00:00Z',
}

SKILL_ASSESSMENT_NEXT_QUESTION_REQUEST_EXAMPLE = {
    'answers': {
        'q-req': 4,
        'q-design': 5,
    },
}

SKILL_ASSESSMENT_NEXT_QUESTION_RESPONSE_EXAMPLE = {
    'next_question': {
        'id': 'q-dev',
        'prompt': 'I can implement features using clear design and coding practices.',
        'dimension_key': 'development',
    },
}
