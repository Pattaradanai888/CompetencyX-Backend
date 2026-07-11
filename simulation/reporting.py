"""Shared text reporting for simulation summaries.

Used by both ``simulate_inmemory`` (pure engine) and ``simulate_assessment``
(DB parity command); optional sections are guarded so either summary shape works.
"""


def write_summary_text(stdout, style, summary: dict[str, object], *, title: str) -> None:
    _write_headline(stdout.write, style, summary, title)
    _write_coverage(stdout.write, style, summary)
    _write_resolved(stdout.write, style, summary)
    _write_low_confidence(stdout.write, style, summary)
    _write_ambiguous(stdout.write, style, summary)


def _write_headline(write, style, summary: dict[str, object], title: str) -> None:
    write(style.MIGRATE_HEADING(f'\n=== {title} (N={summary["samples"]}, seed={summary["seed"]}) ==='))
    if 'likert_weights' in summary:
        write(f'Likert weights: {summary["likert_weights"]}')
    if summary.get('prefix_answers'):
        write(f'Prefix answers: {summary["prefix_answers"]}')
    write(f'Completed:      {summary["completed_count"]:4d} ({summary["completed_rate"] * 100:.1f}%)')
    write(f'Resolved:       {summary["resolved_count"]:4d} ({summary["resolved_rate"] * 100:.1f}%)')
    write(f'Low confidence: {summary["low_confidence_count"]:4d} ({summary["low_confidence_rate"] * 100:.1f}%)')
    write(f'Ambiguous:      {summary["ambiguous_count"]:4d} ({summary["ambiguous_rate"] * 100:.1f}%)')
    if 'answered_role_questions' in summary:
        answered = summary['answered_role_questions']
        write(f'Answered role Qs: mean={answered["mean"]:.2f}  min={answered["min"]}  max={answered["max"]}')
    if 'worst_case_95pct_margin_of_error' in summary:
        write(f'95% worst-case margin of error: +/-{summary["worst_case_95pct_margin_of_error"]:.4f}')


def _write_coverage(write, style, summary: dict[str, object]) -> None:
    write(style.MIGRATE_HEADING('\n--- Role coverage ---'))
    write(
        f'Best-fit roles seen: {summary["best_fit_role_coverage_count"]}/{summary["active_role_count"]} '
        f'({summary["best_fit_role_coverage_rate"] * 100:.1f}%)',
    )
    write(f'Missing best-fit roles: {", ".join(summary["missing_best_fit_roles"]) or "None"}')
    write(
        f'Resolved roles seen: {summary["resolved_role_coverage_count"]}/{summary["active_role_count"]} '
        f'({summary["resolved_role_coverage_rate"] * 100:.1f}%)',
    )
    write(f'Missing resolved roles: {", ".join(summary["missing_resolved_roles"]) or "None"}')
    resolved_shape = summary['resolved_role_uniformity']
    write(
        f'Resolved role uniformity: normalized_entropy={resolved_shape["normalized_entropy"]:.4f}  max_share={resolved_shape["max_share"]:.4f}',
    )


def _write_resolved(write, style, summary: dict[str, object]) -> None:
    if 'resolved_confidence' in summary:
        confidence = summary['resolved_confidence']
        margin = summary['resolved_margin_share']
        score_margin = summary['resolved_score_margin']
        winner = summary['resolved_winner_share']
        write(style.MIGRATE_HEADING('\n--- Resolved sessions ---'))
        write(f'Confidence:        mean={confidence["mean"]:.4f}  min={confidence["min"]:.4f}  median={confidence["median"]:.4f}')
        write(f'Margin (share):    mean={margin["mean"]:.4f}  min={margin["min"]:.4f}  median={margin["median"]:.4f}')
        write(f'Margin (score):    mean={score_margin["mean"]:.4f}  min={score_margin["min"]:.4f}  median={score_margin["median"]:.4f}')
        write(f'Winner share:      mean={winner["mean"]:.4f}  min={winner["min"]:.4f}  median={winner["median"]:.4f}')
        write('Best-fit role distribution:')
        for role, count in summary['resolved_roles'].items():
            write(f'  {role or "None":35s} {count:4d}')


def _write_low_confidence(write, style, summary: dict[str, object]) -> None:
    if 'low_confidence_confidence' in summary:
        confidence = summary['low_confidence_confidence']
        margin = summary['low_confidence_margin_share']
        score_margin = summary['low_confidence_score_margin']
        write(style.WARNING('\n--- Low-confidence completions ---'))
        write(f'Confidence:        mean={confidence["mean"]:.4f}  max={confidence["max"]:.4f}')
        write(f'Margin (share):    mean={margin["mean"]:.4f}  max={margin["max"]:.4f}')
        write(f'Margin (score):    mean={score_margin["mean"]:.4f}  max={score_margin["max"]:.4f}')
        write('Best-fit role distribution:')
        for role, count in list(summary.get('low_confidence_roles', {}).items())[:10]:
            write(f'  {role:35s} {count:4d}')


def _write_ambiguous(write, style, summary: dict[str, object]) -> None:
    if 'ambiguous_confidence' in summary:
        confidence = summary['ambiguous_confidence']
        margin = summary['ambiguous_margin_share']
        score_margin = summary['ambiguous_score_margin']
        write(style.WARNING('\n--- Ambiguous sessions ---'))
        write(f'Confidence:        mean={confidence["mean"]:.4f}  max={confidence["max"]:.4f}')
        write(f'Margin (share):    mean={margin["mean"]:.4f}  max={margin["max"]:.4f}')
        write(f'Margin (score):    mean={score_margin["mean"]:.4f}  max={score_margin["max"]:.4f}')
