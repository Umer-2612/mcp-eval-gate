"""Load a golden-set YAML file into a validated GoldenSetConfig."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import yaml

from mcp_eval_gate.models import GoldenCase, GoldenSetConfig, MatchType, ServerTarget
from mcp_eval_gate.normalize import NormalizeError, parse_normalizers

REQUIRED_CASE_FIELDS = ("id", "tool_name")
CASE_FIELDS = tuple(sorted(f.name for f in fields(GoldenCase)))


class GoldenSetError(ValueError):
    """Raised when a golden-set file is missing, malformed, or fails validation."""


def load_golden_set(path: Path, *, require_expectations: bool = True) -> GoldenSetConfig:
    if not path.exists():
        raise GoldenSetError(f"golden set file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "server" not in raw:
        raise GoldenSetError("golden set file is missing the required `server` block")

    server = _parse_server(raw["server"])
    cases = tuple(_parse_case(raw_case, require_expectations) for raw_case in raw.get("cases") or [])
    _reject_duplicate_ids(cases)

    try:
        normalize = parse_normalizers(raw.get("normalize"))
    except NormalizeError as exc:
        raise GoldenSetError(f"top-level `normalize`: {exc}") from exc

    return GoldenSetConfig(
        server=server,
        cases=cases,
        judge_model=raw.get("judge_model", "claude-sonnet-4-5"),
        normalize=normalize,
        contract_ignore=tuple(raw.get("contract_ignore") or ()),
    )


def require_cases(config: GoldenSetConfig) -> GoldenSetConfig:
    if not config.cases:
        raise GoldenSetError(
            "the golden set has no cases to run. If it was generated from a server's tool list, "
            "uncomment the cases you want and fill in their arguments"
        )
    return config


def _parse_server(raw_server: dict) -> ServerTarget:
    try:
        return ServerTarget(
            command=raw_server.get("command"),
            args=tuple(raw_server.get("args", ())),
            env=raw_server.get("env"),
            url=raw_server.get("url"),
        )
    except ValueError as exc:
        raise GoldenSetError(str(exc)) from exc


def _parse_case(raw_case: dict, require_expectations: bool = True) -> GoldenCase:
    case_id = raw_case.get("id", "<unknown>")
    missing = [field for field in REQUIRED_CASE_FIELDS if field not in raw_case]
    if missing:
        raise GoldenSetError(f"case '{case_id}' is missing required field(s): {', '.join(missing)}")

    unknown = sorted(set(raw_case) - set(CASE_FIELDS))
    if unknown:
        raise GoldenSetError(
            f"case '{case_id}' has unknown field(s): {', '.join(unknown)}. Valid fields: {', '.join(CASE_FIELDS)}"
        )

    raw_match_type = raw_case.get("match_type", MatchType.CONTAINS)
    try:
        match_type = MatchType(raw_match_type)
    except ValueError:
        valid = ", ".join(m.value for m in MatchType)
        raise GoldenSetError(
            f"case '{case_id}' has invalid match_type '{raw_match_type}'. Use one of: {valid}"
        ) from None

    try:
        normalize = parse_normalizers(raw_case.get("normalize"))
    except NormalizeError as exc:
        raise GoldenSetError(f"case '{case_id}': {exc}") from exc
    if not isinstance(raw_case.get("expect_error", False), bool):
        raise GoldenSetError(f"case '{case_id}' has a non-boolean expect_error, use true or false")

    case = GoldenCase(**{**raw_case, "match_type": match_type, "normalize": normalize})
    if require_expectations:
        _require_expectation(case)
    return case


def _require_expectation(case: GoldenCase) -> None:
    if case.match_type == MatchType.EXACT and case.expected_output is None:
        raise GoldenSetError(f"case '{case.id}' uses match_type exact but has no expected_output")
    if case.match_type == MatchType.CONTAINS and not case.expected_output:
        raise GoldenSetError(
            f"case '{case.id}' uses match_type contains but has no expected_output, so it would always pass"
        )
    if case.match_type == MatchType.JUDGE and not case.judge_criteria:
        raise GoldenSetError(f"case '{case.id}' uses match_type judge but has no judge_criteria")
    if case.match_type == MatchType.JUDGE and case.expect_error:
        raise GoldenSetError(f"case '{case.id}' uses match_type judge, which scores successful answers only")


def _reject_duplicate_ids(cases: tuple[GoldenCase, ...]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise GoldenSetError(f"duplicate case id: '{case.id}'")
        seen.add(case.id)
