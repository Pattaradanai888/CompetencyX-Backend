from django.core.management.base import BaseCommand

from roadmaps.seeds import seed_mvp_content


class Command(BaseCommand):
    help = 'Seed the MVP roadmap catalog, prerequisite graph, and question bank.'

    def handle(self, *args, **options):
        seed_mvp_content(stdout=self.stdout)
