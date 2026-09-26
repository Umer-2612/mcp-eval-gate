# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Breaking

- The baseline file is now versioned and holds each case's raw output and the server's contract, not
  only a score. Old `{case_id: score}` files still load, and the next `--update-baseline` upgrades them.
- `match_type: exact` no longer strips surrounding whitespace, so a trailing newline is a difference.
  Add the `trim` normalizer to get the old behavior.
- `run_golden_set` and `load_baseline` return a `GoldenRun` and a `Baseline` instead of a list and a dict.

### Added

- `match_type: snapshot`: compare a tool's output against what `--update-baseline` recorded, with no
  hand-written expected text.
- `expect_error`: a case can require the tool to fail, and the error text still has to match.
- Normalizers (`trim`, `tmp_paths`, `regex`, `ignore_keys`) at the file level and per case, applied to
  both sides of a comparison.
- Contract capture and diff: protocol version, server info, capabilities and every tool from
  `tools/list` are stored in the baseline, and changes are printed as warnings. `--strict-contract`
  fails the run on them, `contract_ignore` silences a path.
- Contract lint: flags a `$schema` other than 2020-12, root-level `allOf`/`if`/`not`, an `inputSchema`
  that is not an object, and structured content that is missing or violates the `outputSchema`.
- `lint` command, to check a server's contract without a golden set.
- `compare` command, to run one golden set against two servers and report differences in output and contract.
- `init --command` and `init --url`, to write a golden set from a live server's tool list. Only
  tools marked read-only are enabled, the rest are commented stubs.
- A GitHub Action (`action.yml`) that runs the gate and writes a job summary, and `--markdown-report`.
- `run_eval_gate` declares tool annotations and takes `strict_contract`.

### Changed

- `run --update-baseline` now refuses to record a baseline while any case fails, and exits 1.
- Exact and substring cases without `expected_output`, and judge cases without `judge_criteria`,
  are rejected. Before, a substring case with no expected text always passed.
- A typo in a case field, or an invalid `match_type`, gives a one-line error that lists the valid
  options, not a raw `TypeError`.
- A server that can't start or that exits immediately gives one readable error (exit code 2)
  instead of a page of traceback.
- `init` with no server writes a golden set that runs as is against the official MCP reference server.
- A corrupt baseline file, or a golden set with no cases, exits 2 with a readable message.

### Added (earlier, unreleased)

- Per-case `timeout_seconds` (default 30). A tool that hangs now fails its own case with a
  "timed out" message instead of stalling the run. Other MCP protocol errors also fail the case
  instead of crashing the run. Prompted by feedback on the Medium article.

## [0.3.0] - 2026-09-24

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

[Unreleased]: https://github.com/Umer-2612/mcp-eval-gate/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Umer-2612/mcp-eval-gate/releases/tag/v0.3.0
[0.2.0]: https://github.com/Umer-2612/mcp-eval-gate/releases/tag/v0.2.0
[0.1.0]: https://github.com/Umer-2612/mcp-eval-gate/releases/tag/v0.1.0
