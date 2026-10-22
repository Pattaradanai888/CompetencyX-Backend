import tempfile
from contextlib import ExitStack
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


COMMAND_MODULE = 'api.management.commands.setup'


def fake_connection(vendor, name):
    connection = mock.MagicMock()
    connection.vendor = vendor
    connection.settings_dict = {'NAME': name, 'HOST': 'db'}
    return connection


class SetupCommandTests(SimpleTestCase):
    def run_setup(self, *args, connection=None, answer=None):
        stdout = StringIO()
        with ExitStack() as stack:
            inner = stack.enter_context(mock.patch(f'{COMMAND_MODULE}.call_command'))
            if connection is not None:
                stack.enter_context(mock.patch(f'{COMMAND_MODULE}.connection', connection))
            if answer is not None:
                stack.enter_context(mock.patch('builtins.input', return_value=answer))
            call_command('setup', *args, stdout=stdout)
        return [call.args[0] for call in inner.call_args_list], stdout.getvalue()

    def test_waits_migrates_then_syncs_content(self):
        steps, output = self.run_setup()
        self.assertEqual(steps, ['wait_for_db', 'migrate', 'sync_content'])
        self.assertIn('Setup complete', output)

    @override_settings(DEBUG=False)
    def test_reset_is_refused_outside_debug(self):
        connection = fake_connection('postgresql', 'competencyx')
        with pytest.raises(CommandError, match='DEBUG is false'):
            self.run_setup('--reset', '--noinput', connection=connection)
        connection.cursor.assert_not_called()

    @override_settings(DEBUG=True)
    def test_reset_asks_first_and_stops_unless_confirmed(self):
        connection = fake_connection('postgresql', 'competencyx')
        with pytest.raises(CommandError, match='cancelled'):
            self.run_setup('--reset', connection=connection, answer='no')
        connection.cursor.assert_not_called()

    @override_settings(DEBUG=True)
    def test_reset_deletes_the_sqlite_file_before_migrating(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'dev.sqlite3'
            database.write_bytes(b'old data')
            steps, output = self.run_setup('--reset', '--noinput', connection=fake_connection('sqlite', database))
            self.assertFalse(database.exists())
        self.assertEqual(steps, ['wait_for_db', 'migrate', 'sync_content'])
        self.assertIn('dropped SQLite file', output)

    @override_settings(DEBUG=True)
    def test_reset_recreates_the_postgres_public_schema(self):
        connection = fake_connection('postgresql', 'competencyx')
        steps, _output = self.run_setup('--reset', connection=connection, answer='yes')
        cursor = connection.cursor.return_value.__enter__.return_value
        self.assertEqual(
            [call.args[0] for call in cursor.execute.call_args_list],
            ['DROP SCHEMA public CASCADE', 'CREATE SCHEMA public'],
        )
        self.assertEqual(steps, ['wait_for_db', 'migrate', 'sync_content'])
