"""Console + HTML rendering for a run, and the pass/fail decision that gates CI."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from bedrock_eval_gate.models import CaseResult, Regression


def exit_code_for(results: list[CaseResult], regressions: list[Regression]) -> int:
    any_failed = any(not r.passed for r in results)
    return 1 if any_failed or regressions else 0


def print_console_report(results: list[CaseResult], regressions: list[Regression]) -> None:
    console = Console()
    table = Table(title="bedrock-eval-gate results")
    table.add_column("Case")
    table.add_column("Score", justify="right")
    table.add_column("Status")
    table.add_column("Detail")

    regressed_ids = {r.case_id for r in regressions}
    for result in results:
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        if result.case_id in regressed_ids:
            status += " [yellow](regression)[/yellow]"
        table.add_row(result.case_id, f"{result.score:.2f}", status, result.detail)

    console.print(table)

    if regressions:
        console.print(f"\n[bold red]{len(regressions)} regression(s) against baseline:[/bold red]")
        for reg in regressions:
            console.print(f"  - {reg.case_id}: {reg.baseline_score:.2f} -> {reg.current_score:.2f} ({reg.detail})")


def write_html_report(results: list[CaseResult], regressions: list[Regression], path: Path) -> None:
    regressed_ids = {r.case_id for r in regressions}
    rows = "\n".join(
        f'<tr class="{"fail" if not r.passed else "pass"}">'
        f"<td>{r.case_id}</td><td>{r.score:.2f}</td>"
        f"<td>{'PASS' if r.passed else 'FAIL'}{' (regression)' if r.case_id in regressed_ids else ''}</td>"
        f"<td>{r.detail}</td></tr>"
        for r in results
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>bedrock-eval-gate report</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
tr.fail {{ background: #fdecea; }}
tr.pass {{ background: #eafaf1; }}
</style></head>
<body>
<h1>bedrock-eval-gate report</h1>
<table>
<tr><th>Case</th><th>Score</th><th>Status</th><th>Detail</th></tr>
{rows}
</table>
</body></html>
"""
    path.write_text(html)
