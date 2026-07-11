import json
from io import StringIO

from django.core.management import call_command
from rest_framework.test import APITestCase


class SimulateAssessmentCommandTests(APITestCase):
    def test_json_output_parses_and_reports_rates(self):
        stdout = StringIO()
        call_command('simulate_assessment', '--samples', '3', '--random-seed', '1', '--format', 'json', stdout=stdout)
        summary = json.loads(stdout.getvalue())
        assert summary['samples'] == 3
        assert 'resolved_rate' in summary
        assert 'resolved_role_coverage_rate' in summary
