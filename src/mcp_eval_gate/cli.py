"""CLI: `mcp-eval-gate run` and `mcp-eval-gate init`."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import anyio
import click

from mcp_eval_gate.baseline import Baseline, BaselineError, load_baseline, save_baseline
from mcp_eval_gate.compare import compare_servers
from mcp_eval_gate.contract import lint_contract
from mcp_eval_gate.discover import fetch_contract, render_golden_set
from mcp_eval_gate.errors import friendly_run_error
from mcp_eval_gate.gate import assess, should_fail
from mcp_eval_gate.golden_set import GoldenSetError, load_golden_set, require_cases
from mcp_eval_gate.judge import build_default_anthropic_client
from mcp_eval_gate.models import ServerTarget
from mcp_eval_gate.report import (
    print_comparison_report,
    print_console_report,
    print_contract_report,
    write_html_report,
    write_markdown_report,
)
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
    "--update-baseline",
    is_flag=True,
    help="Record this run as the baseline (scores, raw outputs, server contract) instead of gating.",
)
@click.option(
    "--strict-contract",
    is_flag=True,
    help="Also fail on contract changes since the baseline and on contract warnings.",
)
@click.option(
    "--html-report", type=click.Path(path_type=Path), default=None, help="Write an HTML report to this path."
)
@click.option(
    "--markdown-report",
    type=click.Path(path_type=Path),
    default=None,
    help="Write a Markdown summary to this path (for example $GITHUB_STEP_SUMMARY).",
)
def run(
    config_path: Path,
    baseline_path: Path,
    update_baseline: bool,
    strict_contract: bool,
    html_report: Path | None,
    markdown_report: Path | None,
) -> None:
    """Run the golden set against a live MCP server and gate on regressions."""
    config = _load_config_or_exit(config_path)
    baseline = Baseline() if update_baseline else _load_baseline_or_exit(baseline_path)

    golden_run = _run_or_exit(
        config,
        anthropic_client=build_default_anthropic_client(),
        recorded_outcomes=baseline.outcomes,
        recording=update_baseline,
    )
    results = golden_run.results

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
        save_baseline(baseline_path, results, contract=golden_run.contract)
        click.secho(f"baseline updated: {baseline_path}", fg="cyan")
        print_console_report(results, regressions=[])
        return

    assessment = assess(golden_run, config, baseline)
    print_console_report(results, assessment.regressions)
    print_contract_report(assessment.contract_changes, assessment.lint_findings)

    if html_report:
        write_html_report(results, assessment.regressions, html_report)
        click.echo(f"html report written to {html_report}")
    if markdown_report:
        write_markdown_report(
            results, assessment.regressions, assessment.contract_changes, assessment.lint_findings, markdown_report
        )

    sys.exit(1 if should_fail(golden_run, assessment, strict_contract=strict_contract) else 0)


def _load_config_or_exit(config_path: Path, *, need_cases: bool = True, require_expectations: bool = True):
    try:
        config = load_golden_set(config_path, require_expectations=require_expectations)
        return require_cases(config) if need_cases else config
    except GoldenSetError as exc:
        click.secho(f"error: {exc}", fg="red", err=True)
        sys.exit(2)


def _load_baseline_or_exit(baseline_path: Path):
    try:
        return load_baseline(baseline_path)
    except BaselineError as exc:
        click.secho(f"error: {exc}", fg="red", err=True)
        sys.exit(2)


def _run_or_exit(config, **kwargs):
    try:
        return anyio.run(lambda: run_golden_set(config, **kwargs))
    except Exception as exc:
        message = friendly_run_error(exc, config.server)
        if message is None:
            raise
        click.secho(f"error: {message}", fg="red", err=True)
        sys.exit(2)


SERVER_OPTIONS = (
    click.option("--command", "command", default=None, help="Server start command, for example 'uvx my-server'."),
    click.option("--url", "url", default=None, help="URL of an HTTP MCP server."),
)


def _server_options(func):
    for option in reversed(SERVER_OPTIONS):
        func = option(func)
    return func


def _target_from_options(command: str | None, url: str | None, *, env: dict[str, str] | None = None):
    if command and url:
        raise click.UsageError("give only one of --command and --url")
    if command:
        parts = shlex.split(command)
        return ServerTarget(command=parts[0], args=tuple(parts[1:]), env=env)
    if url:
        return ServerTarget(url=url)
    return None


@main.command()
@click.option("--out", type=click.Path(path_type=Path), default="golden_set.yaml", show_default=True)
@_server_options
def init(out: Path, command: str | None, url: str | None) -> None:
    """Scaffold a starter golden_set.yaml, from a live server's tool list when one is given."""
    target = _target_from_options(command, url)
    if out.exists():
        click.secho(f"refusing to overwrite existing file: {out}", fg="red", err=True)
        sys.exit(1)
    if target is None:
        out.write_text(SAMPLE_GOLDEN_SET)
    else:
        contract = _fetch_contract_or_exit(target)
        out.write_text(render_golden_set(target, contract))
    click.secho(f"wrote {out}", fg="green")


@main.command()
@_server_options
@click.option(
    "--config", "config_path", type=click.Path(path_type=Path), default=None, help="Use its server block."
)
def lint(command: str | None, url: str | None, config_path: Path | None) -> None:
    """Check a server's declared contract for problems that make clients drop or reject tools."""
    target = _target_from_options(command, url)
    if (target is None) == (config_path is None):
        raise click.UsageError("give exactly one of --command, --url or --config")
    if target is None:
        target = _load_config_or_exit(config_path, need_cases=False).server

    findings = lint_contract(_fetch_contract_or_exit(target))
    if not findings:
        click.secho("no contract warnings", fg="green")
        return
    print_contract_report([], findings)
    sys.exit(1)


@main.command()
@click.option(
    "--config", "config_path", type=click.Path(path_type=Path), default="golden_set.yaml", show_default=True
)
@click.option("--against", "against", default=None, help="Start command of the second server (B).")
@click.option("--against-url", "against_url", default=None, help="URL of the second server (B).")
def compare(config_path: Path, against: str | None, against_url: str | None) -> None:
    """Run the golden set against two servers (A is the config's server) and report what differs."""
    if bool(against) == bool(against_url):
        raise click.UsageError("give exactly one of --against and --against-url")
    config = _load_config_or_exit(config_path, require_expectations=False)
    other = _target_from_options(against, against_url, env=config.server.env)

    try:
        comparison = anyio.run(lambda: compare_servers(config, other))
    except Exception as exc:
        message = friendly_run_error(exc, other) or friendly_run_error(exc, config.server)
        if message is None:
            raise
        click.secho(f"error: {message}", fg="red", err=True)
        sys.exit(2)

    print_comparison_report(comparison)
    sys.exit(0 if comparison.is_identical() else 1)


def _fetch_contract_or_exit(target):
    try:
        return anyio.run(lambda: fetch_contract(target))
    except Exception as exc:
        message = friendly_run_error(exc, target)
        if message is None:
            raise
        click.secho(f"error: {message}", fg="red", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
