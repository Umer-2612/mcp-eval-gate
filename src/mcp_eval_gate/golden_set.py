"""Load a golden-set YAML file into a validated GoldenSetConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from mcp_eval_gate.models import GoldenCase, GoldenSetConfig, MatchType, ServerTarget

REQUIRED_CASE_FIELDS = ("id", "tool_name")


class GoldenSetError(ValueError):
    """Raised when a golden-set file is missing, malformed, or fails validation."""


def load_golden_set(path: Path) -> GoldenSetConfig:
    if not path.exists():
        raise GoldenSetError(f"golden set file not found: {path}")

    raw = yaml.safe_load(path.read_text()) or {}

    if "server" not in raw:
        raise GoldenSetError("golden set file is missing the required `server` block")

    server = _parse_server(raw["server"])
    cases = tuple(_parse_case(raw_case) for raw_case in raw.get("cases", []))
    _reject_duplicate_ids(cases)

    return GoldenSetConfig(
        server=server,
        cases=cases,
        judge_model=raw.get("judge_model", "claude-sonnet-4-5"),
    )


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


def _parse_case(raw_case: dict) -> GoldenCase:
    missing = [field for field in REQUIRED_CASE_FIELDS if field not in raw_case]
    if missing:
        case_id = raw_case.get("id", "<unknown>")
        raise GoldenSetError(f"case '{case_id}' is missing required field(s): {', '.join(missing)}")

    fields = dict(raw_case)
    fields["match_type"] = MatchType(fields.get("match_type", MatchType.CONTAINS))
    return GoldenCase(**fields)


def _reject_duplicate_ids(cases: tuple[GoldenCase, ...]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise GoldenSetError(f"duplicate case id: '{case.id}'")
        seen.add(case.id)
