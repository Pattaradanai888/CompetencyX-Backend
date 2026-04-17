from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from roadmaps.seeds import import_roadmap_snapshot


class Command(BaseCommand):
    help = 'Import a raw roadmap snapshot into normalized topic and prerequisite tables.'

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True)
        parser.add_argument('--role-slug', required=True)
        parser.add_argument('--source', default='roadmap.sh')
        parser.add_argument('--source-version', default='')

    def handle(self, *args, **options):
        snapshot_path = Path(options['path']).resolve()
        if not snapshot_path.exists():
            msg = f'Snapshot path does not exist: {snapshot_path}'
            raise CommandError(msg)

        import_roadmap_snapshot(
            snapshot_path=snapshot_path,
            role_slug=options['role_slug'],
            source=options['source'],
            source_version=options['source_version'],
        )
        self.stdout.write(f'Imported snapshot for role "{options["role_slug"]}" from {snapshot_path}.')
