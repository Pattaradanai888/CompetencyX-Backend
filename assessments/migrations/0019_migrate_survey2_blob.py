# Move Survey 2 state out of AssessmentSession.profile JSON into the
# Survey2Answer / Survey2FeedbackEvent models and the survey2_completed fields.

from django.db import migrations
from django.utils.dateparse import parse_datetime


SURVEY2_KEY = 'survey2'
FEEDBACK_KEY = '_survey2_feedback_applied_question_ids'


def migrate_survey2_blobs(apps, schema_editor):
    AssessmentSession = apps.get_model('assessments', 'AssessmentSession')
    Survey2Answer = apps.get_model('assessments', 'Survey2Answer')
    Survey2FeedbackEvent = apps.get_model('assessments', 'Survey2FeedbackEvent')

    for session in AssessmentSession.objects.exclude(profile={}).iterator():
        profile = session.profile if isinstance(session.profile, dict) else {}
        state = profile.pop(SURVEY2_KEY, None)
        applied_question_ids = profile.pop(FEEDBACK_KEY, None)
        if state is None and applied_question_ids is None:
            continue

        if isinstance(state, dict):
            answers = state.get('answers')
            if isinstance(answers, dict):
                for question_id, value in answers.items():
                    try:
                        int_value = int(value)
                    except (TypeError, ValueError):
                        continue
                    Survey2Answer.objects.update_or_create(
                        session=session,
                        question_id=str(question_id)[:64],
                        defaults={'value': int_value},
                    )
            session.survey2_completed = bool(state.get('completed', False))
            completed_at = state.get('completed_at')
            session.survey2_completed_at = parse_datetime(completed_at) if isinstance(completed_at, str) else None

        if isinstance(applied_question_ids, list):
            for question_id in applied_question_ids:
                Survey2FeedbackEvent.objects.get_or_create(
                    session=session,
                    question_id=str(question_id)[:64],
                )

        session.profile = profile
        session.save(update_fields=['profile', 'survey2_completed', 'survey2_completed_at', 'updated_at'])


def restore_survey2_blobs(apps, schema_editor):
    AssessmentSession = apps.get_model('assessments', 'AssessmentSession')
    Survey2Answer = apps.get_model('assessments', 'Survey2Answer')
    Survey2FeedbackEvent = apps.get_model('assessments', 'Survey2FeedbackEvent')

    session_ids = (
        set(Survey2Answer.objects.values_list('session_id', flat=True))
        | set(Survey2FeedbackEvent.objects.values_list('session_id', flat=True))
        | set(AssessmentSession.objects.filter(survey2_completed=True).values_list('id', flat=True))
    )

    for session in AssessmentSession.objects.filter(id__in=session_ids).iterator():
        profile = dict(session.profile) if isinstance(session.profile, dict) else {}
        completed_at = session.survey2_completed_at.isoformat() if session.survey2_completed_at else None
        if completed_at and completed_at.endswith('+00:00'):
            completed_at = f'{completed_at[:-6]}Z'
        profile[SURVEY2_KEY] = {
            'completed': session.survey2_completed,
            'answers': dict(session.survey2_answers.values_list('question_id', 'value')),
            'completed_at': completed_at,
        }
        profile[FEEDBACK_KEY] = sorted(session.survey2_feedback_events.values_list('question_id', flat=True))
        session.profile = profile
        session.save(update_fields=['profile', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0018_survey2_answer_and_state'),
    ]

    operations = [
        migrations.RunPython(migrate_survey2_blobs, restore_survey2_blobs),
    ]
