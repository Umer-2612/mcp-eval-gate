"""CLI: `mcp-eval-gate run` and `mcp-eval-gate init`."""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import click

from mcp_eval_gate.baseline import diff_against_baseline, load_baseline, save_baseline
from mcp_eval_gate.errors import friendly_run_error
from mcp_eval_gate.golden_set import GoldenSetError, load_golden_set
from mcp_eval_gate.judge import build_default_anthropic_client
from mcp_eval_gate.report import exit_code_for, print_console_report, write_html_report
from mcp_eval_gate.runner import run_golden_set

SAMPLE_GOLDEN_SET = """\
# This runs as is against the official MCP reference server (needs Node.js).
# To test your own server, change `server` and replace the cases below.
server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-everything", "stdio"]
  # or, for an HTTP server instead of stdio:
  # url: http://localhost:3000/mcp

cases:
  - id: echo
    tool_name: echo
    tool_args:
      message: hello
    match_type: contains
    expected_output: "hello"

  - id: get-sum
    tool_name: get-sum
    tool_args:
      a: 12
      b: 30
    match_type: exact
    expected_output: "The sum of 12 and 30 is 42."

  # match_type: judge scores open-ended output with an LLM (needs ANTHROPIC_API_KEY):
  # - id: summary
  #   tool_name: search_docs
  #   tool_args: {query: "data retention policy"}
  #   match_type: judge
  #   judge_criteria: "Answer must state data is retained for 90 days"
  #   min_judge_score: 0.8
"""


@click.group()
def main() -> None:
    """mcp-eval-gate: CI regression gate for MCP servers."""


@main.command()
@click.option(
    "--config", "config_path", type=click.Path(path_type=Path), default="golden_set.yaml", show_default=True
)
@click.option(
    "--baseline", "baseline_path", type=click.Path(path_type=Path), default="baseline.json", show_default=True
)
@click.option(
    "--update-baseline", is_flag=True, help="Overwrite the baseline with this run's scores instead of gating."
)
@click.option(
    "--html-report", type=click.Path(path_type=Path), default=None, help="Write an HTML report to this path."
)
def run(config_path: Path, baseline_path: Path, update_baseline: bool, html_report: Path | None) -> None:
    """Run the golden set against a live MCP server and gate on regressions."""
    try:
        config = load_golden_set(config_path)
    except GoldenSetError as exc:
        click.secho(f"error: {exc}", fg="red", err=True)
        sys.exit(2)

    anthropic_client = build_default_anthropic_client()
    try:
        results = anyio.run(lambda: run_golden_set(config, anthropic_client=anthropic_client))
    except Exception as exc:
        message = friendly_run_error(exc, config.server)
        if message is None:
            raise
        click.secho(f"error: {message}", fg="red", err=True)
        sys.exit(2)

    if update_baseline:
        failed = [r.case_id for r in results if not r.passed]
        if failed:
            print_console_report(results, regressions=[])
            click.secho(
                f"baseline not updated: {len(failed)} case(s) failed ({', '.join(failed)}). "
                "A baseline should record known-good output, so fix these first.",
                fg="red",
            )
            sys.exit(1)
        save_baseline(baseline_path, results)
        click.secho(f"baseline updated: {baseline_path}", fg="cyan")
        print_console_report(results, regressions=[])
        return

    baseline = load_baseline(baseline_path)
    regressions = diff_against_baseline(results, baseline)
    print_console_report(results, regressions)

    if html_report:
        write_html_report(results, regressions, html_report)
        click.echo(f"html report written to {html_report}")

    sys.exit(exit_code_for(results, regressions))


@main.command()
@click.option("--out", type=click.Path(path_type=Path), default="golden_set.yaml", show_default=True)
def init(out: Path) -> None:
    """Scaffold a starter golden_set.yaml."""
    if out.exists():
        click.secho(f"refusing to overwrite existing file: {out}", fg="red", err=True)
        sys.exit(1)
    out.write_text(SAMPLE_GOLDEN_SET)
    click.secho(f"wrote {out}", fg="green")


if __name__ == "__main__":
    main()
