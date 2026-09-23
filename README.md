# bedrock-eval-gate

A CI regression gate for **Amazon Bedrock Knowledge Bases and Agents**. Point it at a
golden set of test cases, run it in CI (or interactively from Claude Code / Cursor via
MCP), and it fails the build when retrieval quality or agent tool-selection regresses
against a committed baseline.

## Why this exists

Bedrock's own Model Evaluation jobs are, in AWS's words, jobs "you gate a pipeline on" —
but wiring that gate is left entirely to the caller. AgentCore Observability (AWS's newer
tracing product) covers the new AgentCore runtime, not classic Bedrock Agents or
Knowledge Bases, which are still where most production Bedrock RAG actually runs. The
generic LLM-ops tools (LangSmith, Langfuse, Arize, Helicone) treat Bedrock as one more
API endpoint — none of them call `Retrieve`/`InvokeAgent` directly or score retrieval
recall against your Knowledge Base.

`bedrock-eval-gate` fills that specific, narrow gap: a golden-set → run → diff-vs-baseline
→ exit-code loop, scoped to classic Bedrock Agents and Knowledge Bases, that a CI job (or
an agent harness) can act on.

## Install

```bash
pip install bedrock-eval-gate
# or, for the MCP server:
pip install "bedrock-eval-gate[mcp]"
```

## Quickstart

```bash
bedrock-eval-gate init                 # scaffolds golden_set.yaml
# edit golden_set.yaml with your KB id / agent id / test cases
bedrock-eval-gate run --update-baseline  # first run: record the baseline
bedrock-eval-gate run                    # subsequent runs: gate on regressions
```

`run` exits non-zero (and prints a diff) if any case fails or regresses against the
baseline — safe to wire directly into a CI job.

## Golden set schema

```yaml
region: us-east-1
knowledge_base_id: KB123ABC
agent_id: AGENT123
agent_alias_id: TSTALIASID
doc_id_metadata_key: doc_id  # metadata key on your KB chunks that holds a stable doc id

cases:
  # Retrieval case: scored deterministically via recall@k, no LLM call needed
  - id: refund-policy-lookup
    type: retrieval
    query: "What is the refund window for enterprise customers?"
    expected_doc_ids: ["doc-42", "doc-7"]
    k: 5
    min_recall: 1.0

  # Agent case: exact tool-call + param match
  - id: cancel-subscription-tool-call
    type: agent
    query: "Cancel my subscription effective immediately"
    expected_tool: cancel_subscription
    expected_params:
      immediate: true

  # Agent case: open-ended answer, scored by Claude-as-judge on Bedrock
  - id: retention-policy-answer
    type: agent
    query: "Summarize our data retention policy"
    judge_criteria: "Answer must state data is retained for 90 days and cite the retention doc"
    min_judge_score: 0.8
```

See `examples/golden_set.yaml` for a runnable copy.

## Use from Claude Code / Cursor (MCP)

```bash
pip install "bedrock-eval-gate[mcp]"
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "bedrock-eval-gate": {
      "command": "bedrock-eval-gate-mcp"
    }
  }
}
```

Then ask your agent things like *"did my last chunking change break retrieval? run the
eval gate"* — it calls the `run_eval_gate` tool directly, before you've committed
anything.

## Use in GitHub Actions

```yaml
- uses: Umer-2612/bedrock-eval-gate/.github/actions/bedrock-eval-gate@v1
  with:
    config: golden_set.yaml
    baseline: baseline.json
```

See `examples/workflow.yml` for a full workflow (OIDC role assumption + PR gating).

## What's explicitly out of scope (v1)

- No hosted dashboard or service — local/CI-invoked only.
- No AgentCore support — this targets classic Bedrock Agents/Knowledge Bases, which
  every other vendor is currently racing *away* from.
- No auto-fix — regressions are surfaced, not silently patched.
- No Terraform/infra integration (tempting, deliberately deferred).

## Development

```bash
uv sync --extra mcp --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests
```

## License

MIT
