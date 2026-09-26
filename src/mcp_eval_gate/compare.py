"""Run one golden set against two servers and report where their behavior differs.

Server A is the `server` block of the golden set, server B is passed in. Every case is treated as
a snapshot: A's output is the reference and B is checked against it, so the question is "did anything
change between these two builds", not "does each one match a hand-written expectation".
Typical uses are an old and a new SDK version, or a release and its candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mcp_eval_gate import runner
from mcp_eval_gate.contract import ContractChange, diff_contract
from mcp_eval_gate.models import CaseResult, GoldenCase, GoldenSetConfig, MatchType, ServerTarget


@dataclass(frozen=True)
class Comparison:
    differences: list[CaseResult]
    compared: int
    skipped: list[str]
    contract_changes: list[ContractChange]

    def is_identical(self) -> bool:
        return not self.differences and not self.contract_changes


async def compare_servers(config: GoldenSetConfig, other: ServerTarget) -> Comparison:
    run_a = await runner.run_golden_set(_as_snapshots(config, expect_error={}), recording=True)
    outcomes_a = {r.case_id: r.outcome for r in run_a.results if r.outcome is not None}
    skipped = [f"{r.case_id}: could not run against A ({r.detail})" for r in run_a.results if r.outcome is None]

    comparable = tuple(case for case in config.cases if case.id in outcomes_a)
    expect_error = {case_id: outcome.is_error for case_id, outcome in outcomes_a.items()}
    config_b = replace(_as_snapshots(replace(config, cases=comparable), expect_error), server=other)
    run_b = await runner.run_golden_set(config_b, recorded_outcomes=outcomes_a)

    ignore = config.contract_ignore
    return Comparison(
        differences=[r for r in run_b.results if not r.passed],
        compared=len(comparable),
        skipped=skipped,
        contract_changes=diff_contract(run_a.contract, run_b.contract, ignore=ignore),
    )


def _as_snapshots(config: GoldenSetConfig, expect_error: dict[str, bool]) -> GoldenSetConfig:
    cases = tuple(
        _snapshot_case(case, expect_error.get(case.id, False)) for case in config.cases
    )
    return replace(config, cases=cases)


def _snapshot_case(case: GoldenCase, expect_error: bool) -> GoldenCase:
    return replace(case, match_type=MatchType.SNAPSHOT, expect_error=expect_error)
