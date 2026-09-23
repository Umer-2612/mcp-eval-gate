"""Load/save a committed baseline and diff a fresh run against it.

A baseline is a simple {case_id: score} snapshot, checked into the repo
alongside the golden set, so "did this change make things worse" is a
git-diffable question instead of a moving target.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_eval_gate.models import CaseResult, Regression

DEFAULT_THRESHOLD = 0.0
IMPLICIT_BASELINE_FOR_NEW_CASES = 1.0


def load_baseline(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_baseline(path: Path, results: list[CaseResult]) -> None:
    baseline = {result.case_id: result.score for result in results}
    path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")


def diff_against_baseline(
    results: list[CaseResult], baseline: dict[str, float], threshold: float = DEFAULT_THRESHOLD
) -> list[Regression]:
    regressions: list[Regression] = []
    seen_case_ids: set[str] = set()

    for result in results:
        seen_case_ids.add(result.case_id)
        baseline_score = baseline.get(result.case_id, IMPLICIT_BASELINE_FOR_NEW_CASES)
        drop = baseline_score - result.score
        if drop > threshold:
            regressions.append(
                Regression(
                    case_id=result.case_id,
                    baseline_score=baseline_score,
                    current_score=result.score,
                    detail=result.detail,
                )
            )

    for case_id, baseline_score in baseline.items():
        if case_id not in seen_case_ids:
            regressions.append(
                Regression(
                    case_id=case_id,
                    baseline_score=baseline_score,
                    current_score=0.0,
                    detail="case present in baseline is missing from the current run",
                )
            )

    return regressions
