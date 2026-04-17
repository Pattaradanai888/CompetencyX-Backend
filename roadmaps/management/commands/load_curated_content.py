from django.core.management.base import BaseCommand

from roadmaps.seeds import load_curated_content


class Command(BaseCommand):
    help = 'Load curated YAML roadmap, prerequisite, and question content.'

    def handle(self, *args, **options):
        load_curated_content(stdout=self.stdout)
