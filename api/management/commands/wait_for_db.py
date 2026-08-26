import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Block until the default database accepts connections, or fail after a timeout.'

    # Railway restarts the Postgres service independently of this one, and a restarted
    # Postgres spends a moment replaying WAL while it answers every connection with
    # "FATAL: the database system is starting up". A deploy that runs migrate straight
    # into that window dies on an OperationalError, so the pre-deploy step waits here
    # first instead.
    default_timeout = 60.0
    default_interval = 2.0

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=float,
            default=self.default_timeout,
            help=f'Seconds to keep retrying before giving up (default: {self.default_timeout:g}).',
        )
        parser.add_argument(
            '--interval',
            type=float,
            default=self.default_interval,
            help=f'Seconds to wait between attempts (default: {self.default_interval:g}).',
        )
        parser.add_argument(
            '--database',
            default='default',
            help='Database alias to wait for (default: default).',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        interval = options['interval']
        alias = options['database']
        connection = connections[alias]

        deadline = time.monotonic() + timeout
        attempt = 0
        while True:
            attempt += 1
            try:
                connection.ensure_connection()
            except OperationalError as exc:
                # A half-open connection object would be reused on the next attempt,
                # so drop it and dial again from scratch.
                connection.close()
                if time.monotonic() + interval > deadline:
                    msg = f'Database {alias!r} was not reachable within {timeout:g}s: {exc}'
                    raise CommandError(msg) from exc
                self.stdout.write(f'Database {alias!r} not ready (attempt {attempt}): {exc}')
                time.sleep(interval)
            else:
                self.stdout.write(self.style.SUCCESS(f'Database {alias!r} is ready.'))
                return
