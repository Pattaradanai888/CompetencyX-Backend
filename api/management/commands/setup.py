import time
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Bring the database up to date in one step: wait for it, migrate, then sync all curated content.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Drop every table first and rebuild from scratch (DEBUG only).')
        parser.add_argument('--noinput', '--no-input', action='store_false', dest='interactive', help='Do not ask before --reset.')
        parser.add_argument('--db-timeout', type=float, default=60.0, help='Seconds to wait for the database (default: 60).')

    def handle(self, *args, **options):
        started = time.perf_counter()
        call_command('wait_for_db', timeout=options['db_timeout'], stdout=self.stdout)
        if options['reset']:
            self._reset(interactive=options['interactive'])
        self._step('migrate', lambda: call_command('migrate', interactive=False, verbosity=0, stdout=self.stdout))
        self._step('sync_content', lambda: call_command('sync_content', stdout=self.stdout))
        self.stdout.write(self.style.SUCCESS(f'Setup complete in {time.perf_counter() - started:.1f}s.'))

    def _step(self, label, run):
        started = time.perf_counter()
        self.stdout.write(self.style.MIGRATE_HEADING(f'== {label}'))
        run()
        self.stdout.write(f'   {label} took {time.perf_counter() - started:.1f}s')

    def _reset(self, *, interactive):
        if not settings.DEBUG:
            msg = 'Refusing --reset because DEBUG is false. Reset a non-development database by hand.'
            raise CommandError(msg)
        target = self._describe_database()
        if interactive:
            answer = input(f'This deletes ALL data in {target}. Type "yes" to continue: ')
            if answer.strip().lower() != 'yes':
                msg = 'Reset cancelled.'
                raise CommandError(msg)
        self._step('reset', self._drop_everything)

    def _describe_database(self):
        name = connection.settings_dict['NAME']
        if connection.vendor == 'sqlite':
            return f'SQLite file {name}'
        host = connection.settings_dict.get('HOST') or 'localhost'
        return f'{connection.vendor} database "{name}" on {host}'

    def _drop_everything(self):
        if connection.vendor == 'sqlite':
            name = str(connection.settings_dict['NAME'])
            connection.close()
            if name == ':memory:' or name.startswith('file:'):
                msg = 'Cannot reset an in-memory SQLite database.'
                raise CommandError(msg)
            try:
                Path(name).unlink(missing_ok=True)
            except PermissionError as exc:
                msg = f'{name} is in use. Stop runserver (or anything else holding it) and try again.'
                raise CommandError(msg) from exc
        elif connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('DROP SCHEMA public CASCADE')
                cursor.execute('CREATE SCHEMA public')
        else:
            msg = f'--reset does not support the {connection.vendor} backend.'
            raise CommandError(msg)
        self.stdout.write(f'   dropped {self._describe_database()}')
