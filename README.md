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
Nothing crashes, the agent using it just gets worse answers. The same goes for the contract a
server declares: a schema dialect some clients reject, a tool a client silently drops, an
error message that stopped explaining what went wrong.

Other tools cover parts of this. The official Inspector's CLI runs scripted single-run
assertions. `mcp-server-diff` compares declared schemas and says it does not test output
correctness. A few other early tools record golden outputs and diff them too, for example
[vexyo](https://github.com/vexyohq/vexyo) and
[cisco-open/mcptoolkit-test](https://github.com/cisco-open/mcptoolkit-test).
`mcp-eval-gate` is another take on golden-output regression, with the server's declared
contract checked next to it.

## How it works

1. `init --command "<how you start your server>"` lists the server's tools and writes a
   `golden_set.yaml` with one case per tool that needs no arguments, and a commented stub for
   the rest.
2. `run --update-baseline` calls every tool and records what came back, once, while
   everything is known to be good. The baseline keeps the raw output, the structured content,
   whether it was an error, and the server's contract.
3. `run` calls the same tools again and compares against the baseline. It prints a table and a
   diff, and exits `1` if anything failed or changed, so any CI job can gate on it.

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
mcp-eval-gate init --command "node dist/index.js"   # writes golden_set.yaml from the live tool list
mcp-eval-gate run --update-baseline                 # first run: record the baseline
mcp-eval-gate run                                   # later runs: gate on changes
```

`init` with no server writes a sample that runs as is against the official MCP reference
server (needs Node.js). `--update-baseline` refuses to record while any case fails, since a
baseline should hold known-good output. Commit `golden_set.yaml` and `baseline.json`.

## Golden set

```yaml
server:
  command: node
  args: ["dist/index.js"]
  # or, for an HTTP server instead of stdio:
  # url: http://localhost:3000/mcp

cases:
  # compare against whatever was recorded in the baseline
  - id: list-projects
    tool_name: list_projects
    match_type: snapshot

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

  # the tool is supposed to fail, and say why
  - id: unknown-user
    tool_name: get_user
    tool_args:
      id: "does-not-exist"
    match_type: contains
    expected_output: "not found"
    expect_error: true

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
| `match_type` | no | `contains` | `snapshot`, `exact`, `contains`, or `judge` |
| `expected_output` | for `exact` and `contains` | | The text to compare against |
| `judge_criteria` | for `judge` | | The rubric the LLM scores against |
| `min_judge_score` | no | `0.8` | Lowest judge score that passes |
| `expect_error` | no | `false` | The case passes only if the tool returns an error, and the error still has to match |
| `normalize` | no | | Normalizers for this case, on top of the file level ones |
| `timeout_seconds` | no | `30` | A case that takes longer fails on its own, so one hung tool does not stall the run |

A tool call that returns an error fails its case, unless the case sets `expect_error`.
`exact` compares character for character, so a trailing newline is a difference and the
failure shows it.

### Normalizers

Output that changes on every run, like timestamps and generated ids, can't be compared as is.
List normalizers at the top of the golden set to apply them to every case, or under a case to
apply them to that one. They run on both sides of a comparison, so the baseline keeps the raw
output.

```yaml
normalize:
  - trim                                   # strip surrounding whitespace
  - tmp_paths                              # /tmp/tmpab12/x becomes <tmp>/x
  - regex: '\d{4}-\d{2}-\d{2}T[\d:.]+Z'    # replace anything that matches
    replace: "<timestamp>"
  - ignore_keys: [id, created_at]          # drop these keys at any depth of JSON output
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every case passed and nothing regressed against the baseline |
| `1` | A case failed or regressed, `--update-baseline` was refused because a case failed, `compare` found a difference, or `lint` found a problem |
| `2` | The golden set or baseline is invalid, or the server could not be started or reached |

## Contract

Each recorded baseline also holds the server's contract: protocol version, server info,
capabilities, and every tool as listed by `tools/list`. On a later run the gate diffs the
current contract against it and prints what changed, for example a tool's `inputSchema`, a
renamed server, a different tool order.

Contract changes are warnings by default. `run --strict-contract` fails the build on them.
To silence a path that is expected to move, such as a version string, list it in the golden set:

```yaml
contract_ignore: [serverInfo.version]
```

The same run also lints the contract and each call's result for things that make clients drop
or reject tools: a `$schema` other than 2020-12, a root-level `allOf` or `if` in an
`inputSchema`, an `inputSchema` that is not an object, and structured content that is missing
or does not match the tool's `outputSchema`.

`lint` does only the contract check, and needs no golden set or baseline:

```bash
mcp-eval-gate lint --command "uvx some-mcp-server"
mcp-eval-gate lint --url http://localhost:3000/mcp
```

## Compare two servers

`compare` runs your golden set against two servers and reports where their behavior differs.
Server A is the `server` block of the golden set, server B is passed on the command line.
Every case is treated as a snapshot, A's output is the reference, so no expected values are
needed. Use it for an old and a new SDK version, or a release and its candidate.

```bash
mcp-eval-gate compare --config golden_set.yaml --against "node dist-next/index.js"
mcp-eval-gate compare --config golden_set.yaml --against-url http://localhost:4000/mcp
```

It also diffs the two contracts, and exits `1` if anything differs.

## GitHub Action

```yaml
- uses: actions/checkout@v4
- uses: Umer-2612/mcp-eval-gate@main
  with:
    config: golden_set.yaml
    baseline: baseline.json
```

It installs the package, runs the gate, and writes the results table to the job summary.
`strict-contract: "true"` also fails on contract changes, and `package` takes a pinned
requirement such as `mcp-eval-gate==0.4.0`. This repository's CI runs the action against a
real server, once expecting a pass and once expecting a failure.

## Run as an MCP tool

The package also installs `mcp-eval-gate-mcp`, an MCP server over stdio with one tool,
`run_eval_gate(config_path, baseline_path, update_baseline, strict_contract)`. Add it to an MCP
client's config:

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

The tool declares its annotations: not read-only (`update_baseline` rewrites a file), it reaches
whatever server the golden set names, and running it twice gives the same result.

## Validation

[`validation/`](https://github.com/Umer-2612/mcp-eval-gate/tree/main/validation) has runs against real servers, each with the actual command
output committed and steps to reproduce it. No paid API calls.

- A one-line regression planted in the official MCP reference server, caught with exit
  code `1` and a real diff.
- [A real bug](https://github.com/Umer-2612/mcp-eval-gate/tree/main/validation/utf8-boundary) the official filesystem server shipped (garbled
  text when a multi-byte character straddled a read boundary), caught by running the commit
  before its upstream fix against a baseline from the fixed commit. The
  [write-up](https://medium.com/@karachiwalaumer2612/mcp-server-testing-in-ci-the-bug-no-schema-check-can-see-39cfce248043)
  walks through it.
- [The same three tools on mcp 1.30.0 and mcp 2.2.0](https://github.com/Umer-2612/mcp-eval-gate/tree/main/validation/sdk-1x-vs-2x).
  `compare` found that 2.x hides the exception message on a failing tool (the text goes from
  `Error executing tool boom: kaboom...` to `Error executing tool boom`), and that the server
  version string is reported differently. Everything else matched. Upgrading the SDK is
  a one-line change that a schema check never sees.

These are small. They show the gate works end to end on real code, not how often this class
of bug occurs.

## Limitations

- Output that varies between runs needs a normalizer, and you write it. There is no automatic
  detection of timestamps or ids.
- `snapshot`, `exact` and `contains` compare the text and structured content a tool returns.
  There is no check of resources or prompts.
- The contract check reads what the server declares. It can't see how a particular client
  reacts to it beyond the lint rules above.
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
