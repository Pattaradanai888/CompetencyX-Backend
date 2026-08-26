from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import SimpleTestCase


class WaitForDbCommandTests(SimpleTestCase):
    """The pre-deploy step depends on this command absorbing a Postgres restart window."""

    def test_returns_immediately_when_the_database_answers(self):
        stdout = StringIO()
        with mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection') as ensure:
            call_command('wait_for_db', stdout=stdout)
        self.assertEqual(ensure.call_count, 1)
        self.assertIn('is ready', stdout.getvalue())

    def test_retries_until_the_database_finishes_starting_up(self):
        stdout = StringIO()
        failure = OperationalError('FATAL:  the database system is starting up')
        with (
            mock.patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
                side_effect=[failure, failure, None],
            ) as ensure,
            mock.patch('api.management.commands.wait_for_db.time.sleep') as sleep,
        ):
            call_command('wait_for_db', '--interval', '0.5', stdout=stdout)
        self.assertEqual(ensure.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(0.5), mock.call(0.5)])
        self.assertIn('is ready', stdout.getvalue())

    def test_gives_up_once_the_timeout_would_be_exceeded(self):
        failure = OperationalError('connection refused')
        with (
            mock.patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
                side_effect=failure,
            ),
            mock.patch('api.management.commands.wait_for_db.time.sleep'),
            pytest.raises(CommandError) as raised,
        ):
            call_command('wait_for_db', '--timeout', '0', '--interval', '0.5', stdout=StringIO())
        self.assertIn('connection refused', str(raised.value))

    def test_closes_the_connection_between_attempts(self):
        failure = OperationalError('starting up')
        with (
            mock.patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
                side_effect=[failure, None],
            ),
            mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.close') as close,
            mock.patch('api.management.commands.wait_for_db.time.sleep'),
        ):
            call_command('wait_for_db', '--interval', '0', stdout=StringIO())
        self.assertEqual(close.call_count, 1)
