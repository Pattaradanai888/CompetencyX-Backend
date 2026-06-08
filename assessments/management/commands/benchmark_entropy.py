import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from assessments.services import _select_question_for_session, create_assessment_session
from roadmaps.models import Question


class Command(BaseCommand):
    help = 'Benchmark Expected Entropy and Core Sequence question selection.'

    def handle(self, *args, **options):
        # 1. Seed if empty
        if not Question.objects.filter(stage=Question.Stage.ROLE, is_active=True).exists():
            self.stdout.write("Seeding MVP content...")
            call_command('seed_mvp_content')

        # Create a session
        session = create_assessment_session()

        # Get candidates
        candidates = list(Question.objects.filter(stage=Question.Stage.ROLE, is_active=True))
        if not candidates:
            self.stdout.write(self.style.ERROR("No candidates found!"))
            return

        self.stdout.write(f"Total role candidates available: {len(candidates)}")

        # 2. Query Count Verification
        self.stdout.write("\n=== 1. DB QUERY COUNT VERIFICATION ===")

        # Run under info_gain with varying candidate counts
        for count in [1, 5, 10, 20, len(candidates)]:
            subset = candidates[:count]
            with override_settings(ASSESSMENT_BANDIT_POLICY_MODE='info_gain'):
                with CaptureQueriesContext(connection) as ctx:
                    _select_question_for_session(session, subset, stage=Question.Stage.ROLE)
                query_count = len(ctx.captured_queries)
                self.stdout.write(f"Candidates: {count:3d} | DB Queries: {query_count}")

        # 4. Prove no DB queries are run inside the loop by wrapping cursor execution
        self.stdout.write("\n=== 2. STRICTLY IN-MEMORY LOOP VERIFICATION ===")
        # We will mock connection.cursor to raise exception on query execution during candidate loop if possible.
        # But even simpler: if DB queries count is perfectly constant (4 queries) regardless of candidate count (1 to 36),
        # this proves mathematically that query count is O(1) and no queries are executed inside the loop.
        # Let's check query logs for count=1 vs count=36.
        with override_settings(ASSESSMENT_BANDIT_POLICY_MODE='info_gain'):
            with CaptureQueriesContext(connection) as ctx1:
                _select_question_for_session(session, candidates[:1], stage=Question.Stage.ROLE)
            with CaptureQueriesContext(connection) as ctx2:
                _select_question_for_session(session, candidates, stage=Question.Stage.ROLE)

            self.stdout.write(f"Queries with 1 candidate: {len(ctx1.captured_queries)}")
            self.stdout.write(f"Queries with {len(candidates)} candidates: {len(ctx2.captured_queries)}")
            if len(ctx1.captured_queries) == len(ctx2.captured_queries):
                self.stdout.write(self.style.SUCCESS("Verification PASSED: Query count is independent of candidate size. Zero DB queries inside candidate loop!"))
            else:
                self.stdout.write(self.style.ERROR("Verification FAILED: Query count depends on candidate size!"))

        # 3. Execution Time Benchmarking
        self.stdout.write("\n=== 3. TIMING BENCHMARKS ===")
        self.stdout.write(f"{'Policy':15} | {'Candidates':10} | {'Time (ms)':10} | {'Queries':8}")
        self.stdout.write("-" * 55)

        policies = ['core_sequence', 'info_gain']
        for policy in policies:
            for count in [5, 10, 20, len(candidates)]:
                subset = candidates[:count]

                # Warmup
                with override_settings(ASSESSMENT_BANDIT_POLICY_MODE=policy):
                    _select_question_for_session(session, subset, stage=Question.Stage.ROLE)

                # Measure time over multiple runs to reduce noise
                runs = 100
                start_time = time.perf_counter()
                for _ in range(runs):
                    with override_settings(ASSESSMENT_BANDIT_POLICY_MODE=policy):
                        _select_question_for_session(session, subset, stage=Question.Stage.ROLE)
                end_time = time.perf_counter()

                avg_time_ms = ((end_time - start_time) / runs) * 1000.0

                with override_settings(ASSESSMENT_BANDIT_POLICY_MODE=policy):
                    with CaptureQueriesContext(connection) as ctx:
                        _select_question_for_session(session, subset, stage=Question.Stage.ROLE)
                    queries = len(ctx.captured_queries)

                self.stdout.write(f"{policy:15} | {count:10d} | {avg_time_ms:10.4f} | {queries:8d}")
