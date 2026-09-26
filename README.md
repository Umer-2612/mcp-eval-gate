<p align="center">
  <a href="https://medium.com/@karachiwalaumer2612/mcp-server-testing-in-ci-the-bug-no-schema-check-can-see-39cfce248043">
    <img src="https://raw.githubusercontent.com/Umer-2612/mcp-eval-gate/main/assets/cover.png" alt="mcp-eval-gate failing a regression: expected the character 界, got garbled characters" width="720"/>
  </a>
</p>

<h1 align="center">mcp-eval-gate</h1>

<p align="center">
  A CI regression gate for MCP servers. It calls your server's tools, compares the results to a
  saved baseline, and fails the build when the output gets worse, even if the schema did not change.
</p>

<p align="center">
  <a href="https://pypi.org/project/mcp-eval-gate/"><img src="https://img.shields.io/pypi/v/mcp-eval-gate?color=39FF88&logo=pypi&logoColor=white" alt="PyPI version"/></a>
  <a href="https://pypi.org/project/mcp-eval-gate/"><img src="https://img.shields.io/pypi/pyversions/mcp-eval-gate?logo=python&logoColor=white" alt="Python versions"/></a>
  <a href="https://github.com/Umer-2612/mcp-eval-gate/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Umer-2612/mcp-eval-gate/ci.yml?branch=main&label=CI" alt="CI status"/></a>
  <a href="https://github.com/Umer-2612/mcp-eval-gate/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Umer-2612/mcp-eval-gate" alt="License"/></a>
  <a href="https://medium.com/@karachiwalaumer2612/mcp-server-testing-in-ci-the-bug-no-schema-check-can-see-39cfce248043"><img src="https://img.shields.io/badge/Medium_Write--up-000000?logo=medium&logoColor=white" alt="Medium write-up"/></a>
  <a href="https://m8ven.ai/mcp/umer-2612/mcp-eval-gate"><img src="https://m8ven.ai/badge/mcp/umer-2612/mcp-eval-gate" alt="M8ven Score"/></a>
</p>

Read the write-up: [MCP server testing in CI: the bug no schema check can see](https://medium.com/@karachiwalaumer2612/mcp-server-testing-in-ci-the-bug-no-schema-check-can-see-39cfce248043).

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

## How it works

1. You describe how to reach your server and list the tool calls that matter, with the output
   you expect from each, in a `golden_set.yaml`.
2. `run --update-baseline` calls every tool and records the results as the baseline, once,
   while everything is known to be good.
3. `run` calls the same tools again and compares against the baseline. It prints a table and a
   diff, and exits `1` if anything failed or got worse, so any CI job can gate on it.

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
record while any case fails, since a baseline should hold known-good output.

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

### Case fields

| Field | Required | Default | Meaning |
|---|---|---|---|
| `id` | yes | | Unique name for the case |
| `tool_name` | yes | | The MCP tool to call |
| `tool_args` | no | `{}` | Arguments passed to the tool |
| `match_type` | no | `contains` | `exact`, `contains`, or `judge` |
| `expected_output` | for `exact` and `contains` | | The text to compare against |
| `judge_criteria` | for `judge` | | The rubric the LLM scores against |
| `min_judge_score` | no | `0.8` | Lowest judge score that passes |
| `timeout_seconds` | no | `30` | A case that takes longer fails on its own, so one hung tool does not stall the run |

A tool call that returns an error always fails its case.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every case passed and nothing regressed against the baseline |
| `1` | A case failed or regressed, or `--update-baseline` was refused because a case failed |
| `2` | The golden set is invalid, or the server could not be started or reached |

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
  before its upstream fix against a baseline from the fixed commit. The
  [write-up](https://medium.com/@karachiwalaumer2612/mcp-server-testing-in-ci-the-bug-no-schema-check-can-see-39cfce248043)
  walks through it.

Both are small. They show the gate works end to end on real code, not how often this class
of bug occurs.

## Limitations

- Matching is exact, substring, or an LLM judge. There is no normalization for volatile
  output such as timestamps or ids, so output that varies between runs can't be compared
  reliably.
- It checks tool outputs only, not schemas or protocol conformance.
- `match_type: judge` has only been tested against a stub client, not the live Anthropic API.

## Feedback

If you maintain an MCP server, I'd like to know what you would want to test and what got in
the way. Open an [issue](https://github.com/Umer-2612/mcp-eval-gate/issues/new/choose) with the
feedback form.

## Development

```bash
uv sync --extra judge --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
```

## License

MIT
