"""CLI: `bedrock-eval-gate run` and `bedrock-eval-gate init`."""

from __future__ import annotations

import sys
from pathlib import Path

import boto3
import click

from bedrock_eval_gate.baseline import diff_against_baseline, load_baseline, save_baseline
from bedrock_eval_gate.golden_set import GoldenSetError, load_golden_set
from bedrock_eval_gate.report import exit_code_for, print_console_report, write_html_report
from bedrock_eval_gate.runner import DEFAULT_JUDGE_MODEL_ID, run_golden_set

SAMPLE_GOLDEN_SET = """\
region: us-east-1
knowledge_base_id: REPLACE_WITH_YOUR_KB_ID
agent_id: REPLACE_WITH_YOUR_AGENT_ID
agent_alias_id: REPLACE_WITH_YOUR_AGENT_ALIAS_ID
doc_id_metadata_key: doc_id

cases:
  - id: example-retrieval-case
    type: retrieval
    query: "What is the refund window for enterprise customers?"
    expected_doc_ids: ["doc-42"]
    k: 5
    min_recall: 1.0

  - id: example-tool-call-case
    type: agent
    query: "Cancel my subscription effective immediately"
    expected_tool: cancel_subscription
    expected_params:
      immediate: true

  - id: example-judge-case
    type: agent
    query: "Summarize our data retention policy"
    judge_criteria: "Answer must state data is retained for 90 days"
    min_judge_score: 0.8
"""


@click.group()
def main() -> None:
    """bedrock-eval-gate: CI regression gate for Bedrock Knowledge Bases and Agents."""


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
@click.option("--judge-model-id", default=DEFAULT_JUDGE_MODEL_ID, show_default=True)
@click.option("--region", default=None, help="Overrides the golden set's `region` field.")
def run(
    config_path: Path,
    baseline_path: Path,
    update_baseline: bool,
    html_report: Path | None,
    judge_model_id: str,
    region: str | None,
) -> None:
    """Run the golden set against live Bedrock resources and gate on regressions."""
    try:
        config = load_golden_set(config_path)
    except GoldenSetError as exc:
        click.secho(f"error: {exc}", fg="red", err=True)
        sys.exit(2)

    resolved_region = region or config.region
    agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=resolved_region)
    bedrock_runtime_client = boto3.client("bedrock-runtime", region_name=resolved_region)

    results = run_golden_set(
        config,
        agent_runtime_client=agent_runtime_client,
        bedrock_runtime_client=bedrock_runtime_client,
        judge_model_id=judge_model_id,
    )

    if update_baseline:
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
