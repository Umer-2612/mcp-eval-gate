"""Load a golden-set YAML file into a validated GoldenSetConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from bedrock_eval_gate.models import CaseType, GoldenCase, GoldenSetConfig

REQUIRED_CASE_FIELDS = ("id", "type", "query")


class GoldenSetError(ValueError):
    """Raised when a golden-set file is missing, malformed, or fails validation."""


def load_golden_set(path: Path) -> GoldenSetConfig:
    if not path.exists():
        raise GoldenSetError(f"golden set file not found: {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    raw_cases = raw.get("cases", [])

    cases = tuple(_parse_case(raw_case) for raw_case in raw_cases)
    _reject_duplicate_ids(cases)

    return GoldenSetConfig(
        cases=cases,
        knowledge_base_id=raw.get("knowledge_base_id"),
        agent_id=raw.get("agent_id"),
        agent_alias_id=raw.get("agent_alias_id"),
        region=raw.get("region"),
        doc_id_metadata_key=raw.get("doc_id_metadata_key", "doc_id"),
    )


def _parse_case(raw_case: dict) -> GoldenCase:
    missing = [field for field in REQUIRED_CASE_FIELDS if field not in raw_case]
    if missing:
        case_id = raw_case.get("id", "<unknown>")
        raise GoldenSetError(f"case '{case_id}' is missing required field(s): {', '.join(missing)}")

    fields = dict(raw_case)
    fields["type"] = CaseType(fields["type"])
    fields["expected_doc_ids"] = tuple(fields.get("expected_doc_ids", ()))
    return GoldenCase(**fields)


def _reject_duplicate_ids(cases: tuple[GoldenCase, ...]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise GoldenSetError(f"duplicate case id: '{case.id}'")
        seen.add(case.id)
