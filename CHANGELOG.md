# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-23

### Added

- Golden-set schema and loader (YAML) for retrieval and agent test cases.
- Deterministic scoring: recall@k for Knowledge Base retrieval, exact tool-call/param
  matching for Agent action groups.
- Claude-as-judge scoring (via Bedrock Converse) for open-ended agent answers against a
  rubric.
- Baseline snapshot + diff engine: flags regressions against a committed `baseline.json`.
- `bedrock-eval-gate` CLI (`run`, `init`) with console and HTML reporting.
- MCP server (`bedrock-eval-gate-mcp`) exposing `run_eval_gate` for interactive use from
  Claude Code / Cursor.
- Composite GitHub Action + example consumer workflow.

[Unreleased]: https://github.com/Umer-2612/bedrock-eval-gate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Umer-2612/bedrock-eval-gate/releases/tag/v0.1.0
