"""Pure unit tests for the scoring service math (no DB)."""

from assessments.services import scoring_service
from roadmaps.questionnaire import ROLE_PROFILE_WEIGHTS


SAMPLE_QUESTION = {
    'id': 1,
    'item_group': 'core',
    'display_order': 1,
    'discriminates_between': [],
    'agree_dimension_signals': {'construction': 1.0, 'application_build': 0.5},
    'disagree_dimension_signals': {'requirements': 1.0, 'people_product': 0.5},
    'trait_positive_dimension': '',
}


def test_score_dimension_overlap_rewards_aligned_profile():
    backend_profile = ROLE_PROFILE_WEIGHTS['backend-developer']
    score = scoring_service.score_dimension_overlap({'construction': 1.0}, backend_profile)
    assert score > 0


def test_score_dimension_overlap_ignores_zero_signal_weight():
    profile = {'construction': 1.0}
    assert scoring_service.score_dimension_overlap({'construction': 0.0}, profile) == 0.0


def test_build_role_shares_uniform_when_no_evidence():
    slugs = ['role-a', 'role-b', 'role-c']
    distribution = scoring_service.build_role_shares({}, slugs)
    assert set(distribution) == set(slugs)
    assert all(abs(value - 1 / 3) < 1e-9 for value in distribution.values())


def test_build_role_shares_concentrates_on_winner():
    slugs = ['role-a', 'role-b']
    distribution = scoring_service.build_role_shares({'role-a': 5.0, 'role-b': 0.0}, slugs)
    assert distribution['role-a'] > distribution['role-b']
    assert distribution['role-a'] > 0.5


def test_compute_role_evidence_snapshot_accumulates_signals():
    answers = [
        {**SAMPLE_QUESTION, 'scale_value': 2},
        {**SAMPLE_QUESTION, 'scale_value': 2},
    ]
    evidence = scoring_service.compute_role_evidence_snapshot(answers)
    assert evidence.dimension_scores['construction'] == 4.0
    assert evidence.dimension_evidence_counts['construction'] == 2
    assert 'backend-developer' in evidence.role_scores


def test_compute_role_evidence_snapshot_neutral_answer_is_no_evidence():
    evidence = scoring_service.compute_role_evidence_snapshot([{**SAMPLE_QUESTION, 'scale_value': 0}])
    assert evidence.dimension_scores == {}


def _snapshot(answered, available=44, answers=None):
    evidence = scoring_service.compute_role_evidence_snapshot(answers or [{**SAMPLE_QUESTION, 'scale_value': 2}])
    return scoring_service.build_role_inference_snapshot(
        evidence,
        active_role_slugs=list(ROLE_PROFILE_WEIGHTS),
        role_names={},
        answered_questions=answered,
        available_questions=available,
    )


def _ranked(*scores):
    return [{'slug': slug, 'fit_score': score} for slug, score in scores]


def _question(question_id, code, agree, *, display_order=1):
    return {
        'id': question_id,
        'code': code,
        'display_order': display_order,
        'agree_dimension_signals': agree,
        'disagree_dimension_signals': {'people_product': 0.3},
    }


def test_build_role_inference_snapshot_shape():
    snapshot = _snapshot(1)
    assert snapshot['top_role_slug'] is not None
    assert snapshot['answered_questions'] == 1
    assert snapshot['question_target'] == scoring_service.ROLE_DISCOVERY_MAX_QUESTIONS
    assert snapshot['is_complete'] is False
    assert isinstance(snapshot['ranked_roles'], list)
    assert len(snapshot['ranked_roles']) == len(ROLE_PROFILE_WEIGHTS)
    assert snapshot['role_candidates'] == snapshot['ranked_roles'][: scoring_service.ROLE_CANDIDATE_COUNT]
    assert 'fit_share' in snapshot['ranked_roles'][0]


def test_question_target_is_the_cap_or_the_whole_pool_when_smaller():
    assert _snapshot(1, available=44)['question_target'] == scoring_service.ROLE_DISCOVERY_MAX_QUESTIONS
    assert _snapshot(1, available=7)['question_target'] == 7


def test_snapshot_is_complete_at_the_cap():
    snapshot = _snapshot(scoring_service.ROLE_DISCOVERY_MAX_QUESTIONS)
    assert snapshot['is_complete'] is True
    assert snapshot['confidence'] == min(1.0, snapshot['score_margin'] / scoring_service.ROLE_CONFIDENCE_FULL_MARGIN)


def test_survey_never_stops_before_the_floor():
    floor = scoring_service.ROLE_DISCOVERY_MIN_QUESTIONS
    assert not scoring_service.is_role_discovery_complete(answered_questions=floor - 1, question_target=25, candidate_margin=100.0)


def test_survey_stops_after_the_floor_once_the_candidates_stand_apart():
    floor = scoring_service.ROLE_DISCOVERY_MIN_QUESTIONS
    gap = scoring_service.ROLE_CANDIDATE_STOP_MARGIN
    assert scoring_service.is_role_discovery_complete(answered_questions=floor, question_target=25, candidate_margin=gap)
    assert not scoring_service.is_role_discovery_complete(answered_questions=floor, question_target=25, candidate_margin=gap - 0.5)


def test_survey_stops_at_the_cap_whatever_the_margin():
    assert scoring_service.is_role_discovery_complete(answered_questions=25, question_target=25, candidate_margin=0.0)


def test_a_pool_smaller_than_the_floor_is_asked_to_the_end():
    assert not scoring_service.is_role_discovery_complete(answered_questions=4, question_target=5, candidate_margin=100.0)
    assert scoring_service.is_role_discovery_complete(answered_questions=5, question_target=5, candidate_margin=0.0)


def test_warm_up_items_come_first_in_their_fixed_order():
    first, second = scoring_service.ROLE_DISCOVERY_WARMUP_CODES[:2]
    questions = [
        _question(1, 'role-rd-other', {'web_frontend': 1.0}, display_order=1),
        _question(2, second, {'android_platform': 1.0}, display_order=2),
        _question(3, first, {'web_frontend': 1.0}, display_order=3),
    ]
    snapshot = {'is_complete': False, 'ranked_roles': _ranked(('frontend-developer', 1.0), ('backend-developer', 1.0))}
    assert scoring_service.select_next_role_question(questions, snapshot)['code'] == first
    assert scoring_service.select_next_role_question([q for q in questions if q['code'] != first], snapshot)['code'] == second


def test_after_warm_up_the_item_separating_close_leaders_is_asked():
    questions = [
        _question(1, 'role-rd-shared', {'construction': 1.0}, display_order=1),
        _question(2, 'role-rd-splits', {'web_frontend': 1.0}, display_order=2),
    ]
    snapshot = {
        'is_complete': False,
        'ranked_roles': _ranked(('frontend-developer', 3.0), ('backend-developer', 3.0), ('full-stack-developer', 2.0), ('qa-engineer', 0.0)),
    }
    assert scoring_service.select_next_role_question(questions, snapshot)['code'] == 'role-rd-splits'


def test_equally_informative_items_go_in_display_order():
    questions = [
        _question(1, 'role-rd-later', {'web_frontend': 1.0}, display_order=9),
        _question(2, 'role-rd-earlier', {'web_frontend': 1.0}, display_order=4),
    ]
    snapshot = {'is_complete': False, 'ranked_roles': _ranked(('frontend-developer', 1.0), ('backend-developer', 1.0))}
    assert scoring_service.select_next_role_question(questions, snapshot)['code'] == 'role-rd-earlier'


def test_no_next_item_once_complete_or_the_pool_is_empty():
    questions = [_question(1, 'role-rd-any', {'web_frontend': 1.0})]
    assert scoring_service.select_next_role_question(questions, {'is_complete': True, 'ranked_roles': []}) is None
    assert scoring_service.select_next_role_question([], {'is_complete': False, 'ranked_roles': []}) is None


def test_role_resolution_status():
    margin = scoring_service.ROLE_DISCOVERY_MIN_SCORE_MARGIN
    status = scoring_service.get_role_resolution_status
    assert status(is_complete=False, best_fit_role_slug='a', score_margin=margin) == 'in_progress'
    assert status(is_complete=True, best_fit_role_slug=None, score_margin=margin) == 'unknown'
    assert status(is_complete=True, best_fit_role_slug='a', score_margin=margin) == 'resolved'
    assert status(is_complete=True, best_fit_role_slug='a', score_margin=margin - 0.5) == 'low_confidence'
