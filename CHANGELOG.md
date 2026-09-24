# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Failure details now show where an output first differs (with short context and both lengths)
  instead of dumping the full expected and actual strings. Found by running against a real
  server bug where the output was over 1,000 characters.

### Added

- Two validation runs against real MCP servers (`validation/`), including a real upstream
  bug reproduced with one script.
- Issue templates for feedback and bug reports.

### Removed

- The composite GitHub Action and example workflow. Neither had been run in a real
  workflow.

## [0.2.0] - 2026-09-23

Renamed from `bedrock-eval-gate` to `mcp-eval-gate` and generalized from an
Amazon-Bedrock-specific tool to a protocol-generic one. The core mechanism (golden set,
deterministic scoring, baseline diffing, CI exit code) carried over largely unchanged;
what changed is what it connects to.

### Changed

- Golden-set schema: cases now target `tool_name` + `tool_args` on a declared MCP
  `server` (stdio command or HTTP url), instead of Bedrock Knowledge Base / Agent fields.
- Scoring: `match_type` (`exact` | `contains` | `judge`) replaces the Bedrock-specific
  recall@k and tool-call-param matching.
- Judge scoring now calls the Anthropic API directly instead of Bedrock's Converse API.
- CLI and MCP server renamed (`mcp-eval-gate`, `mcp-eval-gate-mcp`).

### Added

- A real MCP client (`mcp_client.py`) that connects to any compliant MCP server over
  stdio or streamable HTTP and calls its tools, replacing the boto3-based Bedrock client.

### Removed

- All AWS/boto3/Bedrock-specific code.

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

[Unreleased]: https://github.com/Umer-2612/mcp-eval-gate/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Umer-2612/mcp-eval-gate/releases/tag/v0.2.0
[0.1.0]: https://github.com/Umer-2612/mcp-eval-gate/releases/tag/v0.1.0
