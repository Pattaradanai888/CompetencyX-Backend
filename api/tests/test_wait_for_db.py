from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.utils import OperationalError
from django.test import SimpleTestCase


class WaitForDbCommandTests(SimpleTestCase):
    """The pre-deploy step depends on this command absorbing a Postgres restart window.

    The command is handed a stand-in connection through the module's own
    ``connections`` lookup rather than by patching Django's wrapper class:
    pytest-django assigns its own blocking wrapper to that class's
    ``ensure_connection`` around every non-database test, so a class-level
    patch is ordering-dependent and failed intermittently under ``-n auto``.
    """

    def run_command(self, *args, attempts):
        """Run the command against a connection whose attempts go as listed."""
        connection = mock.Mock(spec_set=BaseDatabaseWrapper)
        connection.ensure_connection.side_effect = attempts
        stdout = StringIO()
        with (
            mock.patch('api.management.commands.wait_for_db.connections', {'default': connection}),
            mock.patch('api.management.commands.wait_for_db.time.sleep') as sleep,
        ):
            call_command('wait_for_db', *args, stdout=stdout)
        return connection, sleep, stdout.getvalue()

    def test_returns_immediately_when_the_database_answers(self):
        connection, _sleep, output = self.run_command(attempts=[None])
        self.assertEqual(connection.ensure_connection.call_count, 1)
        self.assertIn('is ready', output)

    def test_retries_until_the_database_finishes_starting_up(self):
        failure = OperationalError('FATAL:  the database system is starting up')
        connection, sleep, output = self.run_command('--interval', '0.5', attempts=[failure, failure, None])
        self.assertEqual(connection.ensure_connection.call_count, 3)
        self.assertEqual(sleep.call_args_list, [mock.call(0.5), mock.call(0.5)])
        self.assertIn('is ready', output)

    def test_gives_up_once_the_timeout_would_be_exceeded(self):
        failure = OperationalError('connection refused')
        with pytest.raises(CommandError) as raised:
            self.run_command('--timeout', '0', '--interval', '0.5', attempts=failure)
        self.assertIn('connection refused', str(raised.value))

    def test_closes_the_connection_between_attempts(self):
        failure = OperationalError('starting up')
        connection, _sleep, _output = self.run_command('--interval', '0', attempts=[failure, None])
        self.assertEqual(connection.close.call_count, 1)
