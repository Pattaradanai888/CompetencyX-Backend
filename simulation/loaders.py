"""Django-backed catalog loaders shared by simulate_inmemory and tune_scoring."""

from roadmaps.models import Question, Role


def load_questions() -> list[dict]:
    return [
        {
            'id': question.id,
            'display_order': question.display_order,
            'item_group': question.item_group,
            'discriminates_between': list(question.discriminates_between or []),
            'agree_dimension_signals': dict(question.agree_dimension_signals or {}),
            'disagree_dimension_signals': dict(question.disagree_dimension_signals or {}),
            'trait_positive_dimension': question.trait_positive_dimension,
        }
        for question in (
            Question.objects.filter(stage=Question.Stage.ROLE, is_active=True)
            .order_by('display_order', 'id')
            .only(
                'id',
                'display_order',
                'item_group',
                'discriminates_between',
                'agree_dimension_signals',
                'disagree_dimension_signals',
                'trait_positive_dimension',
            )
        )
    ]


def load_roles() -> tuple[list[str], dict[str, str]]:
    rows = list(Role.objects.filter(is_active=True).values_list('slug', 'name'))
    return [slug for slug, _name in rows], dict(rows)


def count_core_questions(questions: list[dict]) -> int:
    return sum(1 for question in questions if question['item_group'] == 'core')
