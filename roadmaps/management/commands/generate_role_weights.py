"""Regenerate roadmaps/role_weights_generated.py from the relevance mapping.

Examples:
    python manage.py generate_role_weights          # rewrite the module
    python manage.py generate_role_weights --check  # exit 1 if stale (CI)
"""

from django.core.management.base import BaseCommand, CommandError

from roadmaps.weight_derivation import (
    GENERATED_MODULE_PATH,
    load_relevance_mapping,
    render_from_mapping,
    validate_relevance_mapping,
)


class Command(BaseCommand):
    help = 'Derive ROLE_PROFILE_WEIGHTS from data/content/role_dimension_relevance.yaml.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true', help='Fail if the generated module is stale instead of writing it.')

    def handle(self, *args, **options):
        from roadmaps.seeds import load_curated_catalog  # noqa: PLC0415 - avoids loading the seed stack at command discovery

        roles_data, _topics, _questions = load_curated_catalog()
        errors = validate_relevance_mapping(load_relevance_mapping(), roles_yaml_entries=roles_data['roles'])
        if errors:
            for error in errors:
                self.stdout.write(self.style.ERROR(f'MAPPING ERROR: {error}'))
            msg = f'{len(errors)} relevance-mapping validation error(s).'
            raise CommandError(msg)

        rendered = render_from_mapping()
        if options['check']:
            on_disk = GENERATED_MODULE_PATH.read_text(encoding='utf-8') if GENERATED_MODULE_PATH.exists() else ''
            if on_disk != rendered:
                msg = 'role_weights_generated.py is stale — run `manage.py generate_role_weights` and review the diff.'
                raise CommandError(msg)
            self.stdout.write(self.style.SUCCESS('role_weights_generated.py is up to date.'))
            return
        GENERATED_MODULE_PATH.write_text(rendered, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Wrote {GENERATED_MODULE_PATH}'))
