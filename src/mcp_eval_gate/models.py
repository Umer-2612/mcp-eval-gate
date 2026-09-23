"""Core data types shared across golden-set loading, scoring, and baseline diffing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CaseType(StrEnum):
    RETRIEVAL = "retrieval"
    AGENT = "agent"


@dataclass(frozen=True)
class GoldenCase:
    id: str
    type: CaseType
    query: str
    knowledge_base_id: str | None = None
    expected_doc_ids: tuple[str, ...] = ()
    k: int = 5
    min_recall: float = 1.0
    agent_id: str | None = None
    agent_alias_id: str | None = None
    expected_tool: str | None = None
    expected_params: dict[str, object] = field(default_factory=dict)
    judge_criteria: str | None = None
    min_judge_score: float = 0.8


@dataclass(frozen=True)
class RetrievalOutcome:
    retrieved_doc_ids: tuple[str, ...]


@dataclass(frozen=True)
class AgentOutcome:
    called_tool: str | None
    called_params: dict[str, object]
    final_answer: str


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
    cases: tuple[GoldenCase, ...]
    knowledge_base_id: str | None = None
    agent_id: str | None = None
    agent_alias_id: str | None = None
    region: str | None = None
    doc_id_metadata_key: str = "doc_id"
