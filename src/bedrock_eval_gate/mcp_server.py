"""MCP server exposing bedrock-eval-gate as a tool callable from Claude Code, Cursor, etc.

Lets an engineer ask "did my chunking/prompt change break retrieval?" from inside
their agent harness, before committing — not just as a CI-only check.
"""

from __future__ import annotations

from pathlib import Path

import boto3
from mcp.server.mcpserver import MCPServer

from bedrock_eval_gate.baseline import diff_against_baseline, load_baseline, save_baseline
from bedrock_eval_gate.golden_set import GoldenSetError, load_golden_set
from bedrock_eval_gate.runner import DEFAULT_JUDGE_MODEL_ID, run_golden_set

mcp = MCPServer("bedrock-eval-gate")


@mcp.tool()
def run_eval_gate(
    config_path: str,
    baseline_path: str = "baseline.json",
    update_baseline: bool = False,
    region: str | None = None,
    judge_model_id: str = DEFAULT_JUDGE_MODEL_ID,
) -> dict:
    """Run a Bedrock golden-set eval and report pass/fail plus any regressions vs. baseline.

    Args:
        config_path: Path to the golden_set.yaml file.
        baseline_path: Path to the committed baseline.json (created by a prior run).
        update_baseline: If true, overwrite the baseline with this run's scores instead of gating.
        region: AWS region override; defaults to the golden set's own `region` field.
        judge_model_id: Bedrock model id used for judge-criteria cases.
    """
    try:
        config = load_golden_set(Path(config_path))
    except GoldenSetError as exc:
        return {"ok": False, "error": str(exc)}

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
        save_baseline(Path(baseline_path), results)
        return {"ok": True, "baseline_updated": True, "cases": _serialize_results(results)}

    baseline = load_baseline(Path(baseline_path))
    regressions = diff_against_baseline(results, baseline)
    any_failed = any(not r.passed for r in results)

    return {
        "ok": not (any_failed or regressions),
        "cases": _serialize_results(results),
        "regressions": [
            {
                "case_id": r.case_id,
                "baseline_score": r.baseline_score,
                "current_score": r.current_score,
                "detail": r.detail,
            }
            for r in regressions
        ],
    }


def _serialize_results(results) -> list[dict]:
    return [{"case_id": r.case_id, "score": r.score, "passed": r.passed, "detail": r.detail} for r in results]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
