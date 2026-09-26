"""Load/save a committed baseline and diff a fresh run against it.

The baseline is checked into the repo next to the golden set, so "did this change make things
worse" is a git-diffable question. Format version 2 keeps each case's score and its raw outcome
(text, structured content, error flag), plus the server's contract when one was captured.
Legacy files, a plain {case_id: score} map, still load.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from mcp_eval_gate.models import CaseResult, Regression, ToolCallOutcome

DEFAULT_THRESHOLD = 0.0
IMPLICIT_BASELINE_FOR_NEW_CASES = 1.0
FORMAT_VERSION = 2


class BaselineError(ValueError):
    """Raised when a baseline file can't be read."""


@dataclass(frozen=True)
class Baseline:
    scores: dict[str, float] = field(default_factory=dict)
    outcomes: dict[str, ToolCallOutcome] = field(default_factory=dict)
    contract: dict | None = None


def load_baseline(path: Path) -> Baseline:
    if not path.exists():
        return Baseline()
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        raise BaselineError(f"baseline file {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BaselineError(f"baseline file {path} is not a JSON object")

    if "version" not in data:
        return Baseline(scores={case_id: float(score) for case_id, score in data.items()})
    if data["version"] > FORMAT_VERSION:
        raise BaselineError(
            f"baseline file {path} was written by a newer mcp-eval-gate (format {data['version']}), please upgrade"
        )

    cases = data.get("cases", {})
    return Baseline(
        scores={case_id: float(entry["score"]) for case_id, entry in cases.items()},
        outcomes={
            case_id: _load_outcome(entry["outcome"]) for case_id, entry in cases.items() if entry.get("outcome")
        },
        contract=data.get("contract"),
    )


def _load_outcome(raw: dict) -> ToolCallOutcome:
    return ToolCallOutcome(text=raw["text"], structured=raw.get("structured"), is_error=bool(raw["is_error"]))


def save_baseline(path: Path, results: list[CaseResult], contract: dict | None = None) -> None:
    data: dict = {"version": FORMAT_VERSION, "cases": {r.case_id: _dump_case(r) for r in results}}
    if contract is not None:
        data["contract"] = contract
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _dump_case(result: CaseResult) -> dict:
    entry: dict = {"score": result.score}
    if result.outcome is not None:
        entry["outcome"] = {
            "is_error": result.outcome.is_error,
            "text": result.outcome.text,
            "structured": result.outcome.structured,
        }
    return entry


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
