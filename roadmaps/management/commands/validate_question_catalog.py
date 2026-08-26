from django.core.management.base import BaseCommand, CommandError

from roadmaps.content_review import is_reviewed
from roadmaps.seeds import load_curated_catalog
from roadmaps.weight_derivation import load_relevance_mapping


class Command(BaseCommand):
    help = 'Validate curated YAML question content without mutating the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--review-report',
            action='store_true',
            help='List questions and relevance-mapping roles still at review.status=draft (informational, exit 0).',
        )
        parser.add_argument(
            '--strict-review',
            action='store_true',
            help='Exit 1 if any question or mapping role is still at review.status=draft (content-freeze check).',
        )

    def handle(self, *args, **options):
        roles_data, topics_data, questions_data = load_curated_catalog()
        total_questions = len(questions_data['role_questions'])
        self.stdout.write(
            self.style.SUCCESS(f'Validated {len(roles_data["roles"])} roles, {len(topics_data["topics"])} topics, and {total_questions} questions.')
        )

        if not (options['review_report'] or options['strict_review']):
            return

        draft_questions = [
            question['code']
            for question in questions_data['role_questions']
            if not is_reviewed(question)
        ]
        mapping = load_relevance_mapping()
        draft_mapping_roles = [
            role_slug
            for role_slug, role_entry in mapping['roles'].items()
            if not is_reviewed(role_entry)
        ]

        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Review status ---'))
        self.stdout.write(f'Questions still draft: {len(draft_questions)}/{total_questions}')
        for code in draft_questions:
            self.stdout.write(f'  {code}')
        self.stdout.write(f'Relevance-mapping roles still draft: {len(draft_mapping_roles)}/{len(mapping["roles"])}')
        for role_slug in draft_mapping_roles:
            self.stdout.write(f'  {role_slug}')

        if options['strict_review'] and (draft_questions or draft_mapping_roles):
            msg = f'{len(draft_questions)} question(s) and {len(draft_mapping_roles)} mapping role(s) are still draft.'
            raise CommandError(msg)
        if not draft_questions and not draft_mapping_roles:
            self.stdout.write(self.style.SUCCESS('All content reviewed.'))
