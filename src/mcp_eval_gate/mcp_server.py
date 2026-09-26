"""MCP server exposing mcp-eval-gate as a tool callable from Claude Code, Cursor, etc.

Lets an engineer ask "did my last change break this MCP server's tools?" from
inside their agent harness, before committing, not just as a CI-only check.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from mcp_eval_gate.baseline import Baseline, BaselineError, load_baseline, save_baseline
from mcp_eval_gate.errors import friendly_run_error
from mcp_eval_gate.gate import assess, should_fail
from mcp_eval_gate.golden_set import GoldenSetError, load_golden_set, require_cases
from mcp_eval_gate.judge import build_default_anthropic_client
from mcp_eval_gate.runner import run_golden_set

# Not read-only (update_baseline rewrites a file), it calls whatever server the golden set
# names and optionally an LLM judge, and running it twice gives the same result.
RUN_EVAL_GATE_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
)

mcp = MCPServer("mcp-eval-gate")


@mcp.tool(annotations=RUN_EVAL_GATE_ANNOTATIONS)
async def run_eval_gate(
    config_path: str,
    baseline_path: str = "baseline.json",
    update_baseline: bool = False,
    strict_contract: bool = False,
) -> dict:
    """Run a golden-set eval against a live MCP server and report regressions vs. baseline.

    Args:
        config_path: Path to the golden_set.yaml file.
        baseline_path: Path to the committed baseline.json (created by a prior run).
        update_baseline: If true, overwrite the baseline with this run instead of gating.
        strict_contract: If true, contract changes since the baseline and contract warnings also fail the run.
    """
    try:
        config = require_cases(load_golden_set(Path(config_path)))
        baseline = Baseline() if update_baseline else load_baseline(Path(baseline_path))
    except (GoldenSetError, BaselineError) as exc:
        return {"ok": False, "error": str(exc)}

    try:
        golden_run = await run_golden_set(
            config,
            anthropic_client=build_default_anthropic_client(),
            recorded_outcomes=baseline.outcomes,
            recording=update_baseline,
        )
    except Exception as exc:
        message = friendly_run_error(exc, config.server)
        if message is None:
            raise
        return {"ok": False, "error": message}

    results = golden_run.results
    if update_baseline:
        failed = [r.case_id for r in results if not r.passed]
        if failed:
            return {
                "ok": False,
                "error": f"baseline not updated: {len(failed)} case(s) failed ({', '.join(failed)}). "
                "A baseline should record known-good output, so fix these first.",
                "cases": _serialize_results(results),
            }
        save_baseline(Path(baseline_path), results, contract=golden_run.contract)
        return {"ok": True, "baseline_updated": True, "cases": _serialize_results(results)}

    assessment = assess(golden_run, config, baseline)
    return {
        "ok": not should_fail(golden_run, assessment, strict_contract=strict_contract),
        "cases": _serialize_results(results),
        "regressions": [
            {
                "case_id": r.case_id,
                "baseline_score": r.baseline_score,
                "current_score": r.current_score,
                "detail": r.detail,
            }
            for r in assessment.regressions
        ],
        "contract_changes": [c.describe() for c in assessment.contract_changes],
        "contract_warnings": assessment.lint_findings,
    }


def _serialize_results(results) -> list[dict]:
    return [{"case_id": r.case_id, "score": r.score, "passed": r.passed, "detail": r.detail} for r in results]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
