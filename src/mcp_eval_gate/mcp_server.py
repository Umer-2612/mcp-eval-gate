"""MCP server exposing mcp-eval-gate as a tool callable from Claude Code, Cursor, etc.

Lets an engineer ask "did my last change break this MCP server's tools?" from
inside their agent harness, before committing, not just as a CI-only check.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from mcp_eval_gate.baseline import diff_against_baseline, load_baseline, save_baseline
from mcp_eval_gate.golden_set import GoldenSetError, load_golden_set
from mcp_eval_gate.judge import build_default_anthropic_client
from mcp_eval_gate.runner import run_golden_set

mcp = MCPServer("mcp-eval-gate")


@mcp.tool()
async def run_eval_gate(
    config_path: str,
    baseline_path: str = "baseline.json",
    update_baseline: bool = False,
) -> dict:
    """Run a golden-set eval against a live MCP server and report regressions vs. baseline.

    Args:
        config_path: Path to the golden_set.yaml file.
        baseline_path: Path to the committed baseline.json (created by a prior run).
        update_baseline: If true, overwrite the baseline with this run's scores instead of gating.
    """
    try:
        config = load_golden_set(Path(config_path))
    except GoldenSetError as exc:
        return {"ok": False, "error": str(exc)}

    anthropic_client = build_default_anthropic_client()
    results = await run_golden_set(config, anthropic_client=anthropic_client)

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
