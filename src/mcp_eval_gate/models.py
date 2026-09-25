"""Core data types shared across golden-set loading, MCP calls, scoring, and baseline diffing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MatchType(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"
    JUDGE = "judge"


@dataclass(frozen=True)
class ServerTarget:
    """How to reach the MCP server under test: a stdio subprocess or a URL."""

    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if bool(self.command) == bool(self.url):
            raise ValueError("ServerTarget needs exactly one of `command` (stdio) or `url` (HTTP)")


@dataclass(frozen=True)
class GoldenCase:
    id: str
    tool_name: str
    tool_args: dict[str, object] = field(default_factory=dict)
    match_type: MatchType = MatchType.CONTAINS
    expected_output: str | None = None
    judge_criteria: str | None = None
    min_judge_score: float = 0.8
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class ToolCallOutcome:
    text: str
    structured: dict | None
    is_error: bool


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    score: float
    passed: bool
    detail: str


@dataclass(frozen=True)
class Regression:
    case_id: str
    baseline_score: float
    current_score: float
    detail: str


@dataclass(frozen=True)
class GoldenSetConfig:
    server: ServerTarget
    cases: tuple[GoldenCase, ...]
    judge_model: str = "claude-sonnet-4-5"
