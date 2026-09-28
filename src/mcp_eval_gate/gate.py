"""Turns a finished run plus a baseline into the verdict shared by the CLI and the MCP tool."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_eval_gate.baseline import Baseline, diff_against_baseline
from mcp_eval_gate.contract import ContractChange, diff_contract, lint_call, lint_contract
from mcp_eval_gate.models import GoldenSetConfig, Regression
from mcp_eval_gate.runner import GoldenRun


@dataclass(frozen=True)
class Assessment:
    regressions: list[Regression]
    contract_changes: list[ContractChange]
    lint_findings: list[str]

    def has_contract_problems(self) -> bool:
        return bool(self.contract_changes or self.lint_findings)


def assess(run: GoldenRun, config: GoldenSetConfig, baseline: Baseline) -> Assessment:
    changes = (
        diff_contract(baseline.contract, run.contract, ignore=config.contract_ignore)
        if baseline.contract is not None
        else []
    )
    return Assessment(
        regressions=diff_against_baseline(run.results, baseline.scores),
        contract_changes=changes,
        lint_findings=lint_run(run, config),
    )


def lint_run(run: GoldenRun, config: GoldenSetConfig) -> list[str]:
    findings = lint_contract(run.contract)
    tool_by_case = {case.id: case.tool_name for case in config.cases}
    for result in run.results:
        if result.outcome is not None:
            findings.extend(lint_call(tool_by_case[result.case_id], result.outcome, run.contract))
    return list(dict.fromkeys(findings))


def should_fail(run: GoldenRun, assessment: Assessment, *, strict_contract: bool) -> bool:
    if any(not r.passed for r in run.results) or assessment.regressions:
        return True
    return strict_contract and assessment.has_contract_problems()
