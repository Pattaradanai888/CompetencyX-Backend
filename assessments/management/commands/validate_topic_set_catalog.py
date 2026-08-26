"""Report what the Assessable Topic Set catalog is missing.

Coverage of the imported graph is deliberately not required: a node belonging
to no set stays Unassessed and is reported as a review backlog rather than
failing the run (ADR-0003). The findings that are content errors -- a set
pointing at a node that does not exist, a set whose Canonical Thai Wording a
person has not yet reviewed -- are reported the same way, and only
``--strict`` turns any of it into a failure.

"Not yet reviewed" is read off the set's ``review.status``, never off whether
it has Thai text: this is the human gate of the topic-set review made
mechanical. A draft set is still synced and asked in the meantime (ADR-0004).
"""

from django.core.management.base import BaseCommand, CommandError

from assessments.services.assessable_topic_set_service import build_topic_set_report


class Command(BaseCommand):
    help = 'Report gaps in the authored Assessable Topic Set catalog without mutating the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Exit 1 if any role has no sets, any set points at a missing node, or any set is not yet review.status=reviewed.',
        )

    def handle(self, *args, **options):
        report = build_topic_set_report()

        self.stdout.write(
            self.style.SUCCESS(f'Validated {report["set_count"]} Assessable Topic Sets across {len(report["roles_with_sets"])} roles.')
        )

        self._write_section('Roles with no Assessable Topic Set', report['roles_without_sets'])
        self._write_section(
            'Sets pointing at nodes that do not exist',
            [f'{set_key}: {", ".join(slugs)}' for set_key, slugs in report['unknown_node_slugs']],
        )
        self._write_section('Sets not yet reviewed', report['sets_not_reviewed'])

        # Counted by slug: a slug is how a set addresses a node, so two nodes
        # sharing one are covered or uncovered together.
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Backlog: roadmap node slugs belonging to no set ---'))
        for role_slug, count in report['uncovered_node_counts']:
            self.stdout.write(f'  {role_slug}: {count}')
        self.stdout.write(f'Total uncovered node slugs: {report["uncovered_node_total"]} (backlog, not a failure)')

        blocking = report['roles_without_sets'] or report['unknown_node_slugs'] or report['sets_not_reviewed']
        if options['strict'] and blocking:
            msg = (
                f'{len(report["roles_without_sets"])} role(s) with no sets, '
                f'{len(report["unknown_node_slugs"])} set(s) with unknown nodes, and '
                f'{len(report["sets_not_reviewed"])} set(s) not yet reviewed.'
            )
            raise CommandError(msg)
        if not blocking:
            self.stdout.write(self.style.SUCCESS('Every active role has reviewed sets and every set resolves.'))

    def _write_section(self, heading: str, lines: list[str]):
        self.stdout.write(self.style.MIGRATE_HEADING(f'\n--- {heading}: {len(lines)} ---'))
        for line in lines:
            self.stdout.write(f'  {line}')
