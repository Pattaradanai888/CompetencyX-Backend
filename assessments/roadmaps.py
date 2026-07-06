from .models import Survey2Dimension, Survey2Question, Survey2RoleGuidance


def get_survey2_catalog(role_slug: str | None = None) -> dict[str, object]:
    return {
        'version': '2026-05-11.psp-sdlc-v1',
        'scale': [
            {'label': 'Strongly disagree', 'label_th': 'ไม่เห็นด้วยอย่างยิ่ง', 'value': 1},
            {'label': 'Disagree', 'label_th': 'ไม่เห็นด้วย', 'value': 2},
            {'label': 'Neutral', 'label_th': 'เป็นกลาง', 'value': 3},
            {'label': 'Agree', 'label_th': 'เห็นด้วย', 'value': 4},
            {'label': 'Strongly agree', 'label_th': 'เห็นด้วยอย่างยิ่ง', 'value': 5},
        ],
        'dimensions': list_survey2_dimensions(),
        'questions': list_survey2_questions(),
        'role_guidance': list_survey2_role_guidance(role_slug),
    }


def get_survey2_question_ids() -> set[str]:
    return {question['id'] for question in list_survey2_questions()}


def list_survey2_questions() -> list[dict[str, object]]:
    return [
        {
            'id': question['question_id'],
            'prompt': question['prompt'],
            'translations': {
                'en': {'prompt': question['prompt']},
                **(question['translations'] or {}),
            },
            'dimension_key': question['dimension_key'],
            'display_order': question['display_order'],
        }
        for question in Survey2Question.objects.filter(is_active=True)
        .order_by('display_order', 'question_id')
        .values('question_id', 'prompt', 'translations', 'dimension_key', 'display_order')
    ]


def list_survey2_dimensions() -> list[dict[str, object]]:
    return [
        {
            'key': dimension['dimension_key'],
            'label': dimension['label'],
            'track': dimension['track'],
            'low_score_action': dimension['low_score_action'],
        }
        for dimension in Survey2Dimension.objects.filter(is_active=True)
        .order_by('display_order', 'dimension_key')
        .values('dimension_key', 'label', 'track', 'low_score_action')
    ]


def list_survey2_role_guidance(role_slug: str | None = None) -> list[str]:
    if role_slug:
        role_guidance = list(
            Survey2RoleGuidance.objects.filter(role__slug=role_slug, is_active=True)
            .order_by('display_order', 'id')
            .values_list('guidance', flat=True)
        )
        if role_guidance:
            return role_guidance

    return list(
        Survey2RoleGuidance.objects.filter(role__isnull=True, is_active=True)
        .order_by('display_order', 'id')
        .values_list('guidance', flat=True)
    )
