from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.services.skill_assessment_catalog_service import sync_skill_assessment_catalog
from roadmaps.seeds import load_curated_content


class Command(BaseCommand):
    help = 'Synchronize all curated Role Discovery, roadmap, and Skill Assessment content.'

    @transaction.atomic
    def handle(self, *args, **options):
        load_curated_content(stdout=self.stdout)
        sync_skill_assessment_catalog(stdout=self.stdout)
