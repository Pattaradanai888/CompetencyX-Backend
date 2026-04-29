from django.core.management.base import BaseCommand

from roadmaps.seeds import load_curated_catalog


class Command(BaseCommand):
    help = 'Validate curated YAML question content without mutating the database.'

    def handle(self, *args, **options):
        roles_data, topics_data, questions_data = load_curated_catalog()
        total_questions = len(questions_data['role_questions']) + len(questions_data['skill_questions'])
        self.stdout.write(
            self.style.SUCCESS(f'Validated {len(roles_data["roles"])} roles, {len(topics_data["topics"])} topics, and {total_questions} questions.')
        )
