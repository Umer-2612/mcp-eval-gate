# mcp-eval-gate

A CI regression gate for MCP servers. Give it a golden set of tool calls with known-good
outputs, run it in CI or from Claude Code / Cursor over MCP, and it fails the build when
a tool's actual output gets worse compared to a saved baseline, even if the tool's schema
never changed.

## Why

An MCP server's tool names and input schemas can stay identical while what the tool
actually returns quietly gets worse: a chunking change degrades search results, a
refactor breaks a code path, a dependency bump changes behavior. Nothing crashes, the
agent using it just starts getting worse answers.

The official Inspector tool has a CI mode, but it checks one run against a rule, not
against what a good run looked like last week. A community tool for diffing MCP servers
exists too, but its own README says plainly it only compares declared schemas, not actual
output values. `mcp-eval-gate` does the other half: it calls your server's tools with real
arguments, scores the result, compares it to a committed baseline, and exits non-zero if
anything got worse.

## Install

```bash
pip install mcp-eval-gate
# add [judge] if any cases use match_type: judge (LLM-scored open-ended output)
pip install "mcp-eval-gate[judge]"
```

## Quickstart

```bash
mcp-eval-gate init                   # scaffolds golden_set.yaml
# edit golden_set.yaml with how to reach your server and your test cases
mcp-eval-gate run --update-baseline  # first run: record the baseline
mcp-eval-gate run                    # subsequent runs: gate on regressions
```

`run` exits non-zero and prints a diff if any case fails or regresses against the
baseline. Wire it directly into a CI job.

## Golden set schema

```yaml
server:
  command: node
  args: ["dist/index.js"]
  # or, for an HTTP server instead of stdio:
  # url: http://localhost:3000/mcp

judge_model: claude-sonnet-4-5 # only used by match_type: judge cases

cases:
  # Substring match: cheap, deterministic, no model call
  - id: get-weather-nyc
    tool_name: get_weather
    tool_args:
      city: "New York"
    match_type: contains
    expected_output: "New York"

  # Exact match, useful for structured or short deterministic outputs
  - id: cancel-subscription
    tool_name: cancel_subscription
    tool_args:
      immediate: true
    match_type: exact
    expected_output: "cancelled"

  # Open-ended output, scored by Claude against a rubric
  - id: retention-policy-answer
    tool_name: search_docs
    tool_args:
      query: "data retention policy"
    match_type: judge
    judge_criteria: "Answer must state data is retained for 90 days"
    min_judge_score: 0.8
```

See `examples/golden_set.yaml` for a runnable copy. A tool call that errors always fails
the case, regardless of match_type.

## Use from Claude Code / Cursor (MCP)

```bash
pip install "mcp-eval-gate[judge]"
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "mcp-eval-gate": {
      "command": "mcp-eval-gate-mcp"
    }
  }
}
```

Then ask your agent something like *"did my last change break this server's tools? run
the eval gate"*. It calls the `run_eval_gate` tool directly, before you've committed
anything.

## Use in GitHub Actions

```yaml
- uses: Umer-2612/mcp-eval-gate/.github/actions/mcp-eval-gate@v1
  with:
    config: golden_set.yaml
    baseline: baseline.json
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }} # only for match_type: judge cases
```

See `examples/workflow.yml` for a full workflow.

## Scope

In v1:

- Works against any compliant MCP server, stdio or HTTP, in any language.
- Local or CI-invoked only, no hosted dashboard.
- Regressions are surfaced, not auto-fixed.

Not in v1: a visual trace UI (Inspector already does that well), auto-generating a golden
set from server introspection.

## Development

```bash
uv sync --extra judge --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
```

## License

MIT
