# Validation

Two runs against real MCP servers, both free to reproduce and both using the committed
transcripts as evidence.

| Run | What it shows | Where |
|---|---|---|
| 1. Planted regression | End to end works against the official reference server | this page |
| 2. Real historical bug | Catches a bug the official filesystem server actually shipped | [`utf8-boundary/`](utf8-boundary/) |

## Validation 1: a planted regression in the reference server

This is a real run, not a claim. Everything here is free to reproduce: no paid API
calls, no account, no published bug in anyone else's project. All `match_type: judge`
cases are excluded from this validation on purpose, so it never touches a paid model API.

### What server this ran against

[`@modelcontextprotocol/server-everything`](https://github.com/modelcontextprotocol/servers/tree/main/src/everything),
the official MCP reference server maintained by the Model Context Protocol team, built
from source at commit
[`f46d957`](https://github.com/modelcontextprotocol/servers/commit/f46d9578190b476b3501923ea8977d899e8db2cb).

### Step 1: a clean run against the real server

Run everything from inside `validation/`, because `golden_set.yaml` points at
`servers/src/everything/dist/index.js` by relative path.

```bash
git clone https://github.com/modelcontextprotocol/servers.git
cd servers && git checkout f46d9578190b476b3501923ea8977d899e8db2cb   # pinned so the patch applies
cd src/everything && npm ci && npm run build
cd ../../..                                                          # back in validation/
mcp-eval-gate run --config golden_set.yaml --baseline baseline.json --update-baseline
```

Real output, `golden_set.yaml` in this directory, `clean-run.log`:

```
Starting default (STDIO) server...
                        mcp-eval-gate results                        
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Case                       ┃ Score ┃ Status ┃ Detail              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ echo-basic                 │  1.00 │ PASS   │ expected text found │
│ get-sum-basic              │  1.00 │ PASS   │ exact match         │
│ get-sum-negative           │  1.00 │ PASS   │ exact match         │
│ get-structured-content-nyc │  1.00 │ PASS   │ expected text found │
└────────────────────────────┴───────┴────────┴─────────────────────┘
```

Exit code `0`. `baseline.json` in this directory is exactly what that run wrote.

### Step 2: a controlled regression, applied on purpose

`demo-regression.patch` is a one-line change to `get-sum.ts`: it adds `+ 1` to the sum.
The tool's name and input schema stay identical, only the returned value changes, which
is exactly the failure mode a schema-diff tool cannot catch. Apply it and rebuild:

```bash
cd servers && git apply ../demo-regression.patch
cd src/everything && npm run build
cd ../../..
mcp-eval-gate run --config golden_set.yaml --baseline baseline.json
```

Real output, `regression-run.log`:

```
Starting default (STDIO) server...
                             mcp-eval-gate results                              
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Case                   ┃ Score ┃ Status            ┃ Detail                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ echo-basic             │  1.00 │ PASS              │ expected text found     │
│ get-sum-basic          │  0.00 │ FAIL (regression) │ expected exactly 'The   │
│                        │       │                   │ sum of 12 and 30 is     │
│                        │       │                   │ 42.', got 'The sum of   │
│                        │       │                   │ 12 and 30 is 43.'       │
│ get-sum-negative       │  0.00 │ FAIL (regression) │ expected exactly 'The   │
│                        │       │                   │ sum of -5 and 5 is 0.', │
│                        │       │                   │ got 'The sum of -5 and  │
│                        │       │                   │ 5 is 1.'                │
│ get-structured-conten… │  1.00 │ PASS              │ expected text found     │
└────────────────────────┴───────┴───────────────────┴─────────────────────────┘

2 regression(s) against baseline:
  - get-sum-basic: 1.00 -> 0.00 (expected exactly 'The sum of 12 and 30 is 42.',
got 'The sum of 12 and 30 is 43.')
  - get-sum-negative: 1.00 -> 0.00 (expected exactly 'The sum of -5 and 5 is
0.', got 'The sum of -5 and 5 is 1.')
```

Exit code `1`. Two cases flagged, `get-structured-content-nyc` correctly left alone
since it doesn't touch `get-sum`. This is the shape of bug the project exists for: no
crash, no schema change, no error, just a wrong number that a CI job now catches instead
of a user.

### What this does and doesn't prove

Does: the client works against a real, official, third-party MCP server; the scoring and
baseline-diff logic catches a genuine silent output regression end to end, not just in
the test suite's fakes.

Doesn't: this is not a reported bug in `modelcontextprotocol/servers`, the regression was
introduced locally on a throwaway branch specifically to validate the gate, and reverted
immediately after. No issue was filed against that project.
