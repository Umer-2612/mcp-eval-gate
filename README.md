# mcp-eval-gate

A CI regression gate for MCP servers. You write a golden set of tool calls with known-good
outputs. `mcp-eval-gate` calls those tools on your server, compares the results to a saved
baseline, and exits non-zero if anything got worse, even when the tool's schema did not
change.

## Why

An MCP server's tool names and input schemas can stay identical while what a tool returns
quietly gets worse: a refactor breaks a code path, a dependency bump changes behavior.
Nothing crashes, the agent using it just gets worse answers.

Other tools cover parts of this. The official Inspector's CLI runs scripted single-run
assertions. `mcp-server-diff` compares declared schemas and says it does not test output
correctness. A few other early tools record golden outputs and diff them too, for example
[vexyo](https://github.com/vexyohq/vexyo) and
[cisco-open/mcptoolkit-test](https://github.com/cisco-open/mcptoolkit-test).
`mcp-eval-gate` is another take on golden-output regression.

## Install

Requires Python 3.12+.

```bash
pip install mcp-eval-gate

# only if you use match_type: judge
pip install "mcp-eval-gate[judge]"

# or run it without installing
uvx mcp-eval-gate --help
```

## Quickstart

```bash
mcp-eval-gate init                   # scaffolds golden_set.yaml, which runs as is against the
                                     # official MCP reference server (needs Node.js)
mcp-eval-gate run --update-baseline  # first run: record the baseline
mcp-eval-gate run                    # later runs: gate on regressions
```

Then point `server` at your own server and replace the cases. `--update-baseline` refuses to
record while any case fails, since a baseline should hold known-good output. Exact and
substring cases need an `expected_output`, and judge cases need `judge_criteria`.

`run` prints a table and a diff, and exits `1` if any case fails or regresses against the
baseline. A tool call that returns an error always fails its case. Each case also times out
after 30 seconds (set `timeout_seconds` on a case to change it), and a timeout fails only that
case, so one hung tool does not stall the whole run.

## Golden set

```yaml
server:
  command: node
  args: ["dist/index.js"]
  # or, for an HTTP server instead of stdio:
  # url: http://localhost:3000/mcp

cases:
  # substring match
  - id: get-weather-nyc
    tool_name: get_weather
    tool_args:
      city: "New York"
    match_type: contains
    expected_output: "New York"

  # exact match
  - id: cancel-subscription
    tool_name: cancel_subscription
    tool_args:
      immediate: true
    match_type: exact
    expected_output: "cancelled"

  # scored by an LLM against a rubric (needs ANTHROPIC_API_KEY)
  - id: retention-policy-answer
    tool_name: search_docs
    tool_args:
      query: "data retention policy"
    match_type: judge
    judge_criteria: "Answer must state data is retained for 90 days"
    min_judge_score: 0.8
```

[`examples/golden_set.yaml`](https://github.com/Umer-2612/mcp-eval-gate/blob/main/examples/golden_set.yaml) is a copy you can edit.

## Run as an MCP tool

The package also installs `mcp-eval-gate-mcp`, an MCP server over stdio with one tool,
`run_eval_gate(config_path, baseline_path, update_baseline)`. Add it to an MCP client's config:

```json
{
  "mcpServers": {
    "mcp-eval-gate": { "command": "mcp-eval-gate-mcp" }
  }
}
```

Without installing, use `uvx`:

```json
{
  "mcpServers": {
    "mcp-eval-gate": { "command": "uvx", "args": ["--from", "mcp-eval-gate", "mcp-eval-gate-mcp"] }
  }
}
```

## Validation

[`validation/`](https://github.com/Umer-2612/mcp-eval-gate/tree/main/validation) has two runs against real servers, each with the actual command
output committed and steps to reproduce it. No paid API calls.

- A one-line regression planted in the official MCP reference server, caught with exit
  code `1` and a real diff.
- [A real bug](https://github.com/Umer-2612/mcp-eval-gate/tree/main/validation/utf8-boundary) the official filesystem server shipped (garbled
  text when a multi-byte character straddled a read boundary), caught by running the commit
  before its upstream fix against a baseline from the fixed commit.

Both are small. They show the gate works end to end on real code, not how often this class
of bug occurs.

## Limitations

- Matching is exact, substring, or an LLM judge. There is no normalization for volatile
  output such as timestamps or ids, so output that varies between runs can't be compared
  reliably.
- It checks tool outputs only, not schemas or protocol conformance.
- `match_type: judge` has only been tested against a stub client, not the live Anthropic API.

## Development

```bash
uv sync --extra judge --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
```

## License

MIT
