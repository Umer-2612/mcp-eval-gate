# Validation 2: a real bug in a real server

Validation 1 used a regression I planted on purpose. This one uses a bug the official
MCP filesystem server actually shipped, fixed upstream in
[modelcontextprotocol/servers#4667](https://github.com/modelcontextprotocol/servers/pull/4667).
Free to run, no API keys, no changes to anyone else's code.

## The bug

`read_text_file` with `head` or `tail` reads the file in 1024-byte chunks. When a
multi-byte UTF-8 character straddled a chunk boundary, the tool didn't error. It returned
garbled text (`���` in place of `界`). The tool name and schema were unchanged, so a
schema-diff tool sees nothing.

## What the run does

1. Build the filesystem server at the fix commit
   [`11845d5`](https://github.com/modelcontextprotocol/servers/commit/11845d51cbb42cba9695566f9134f5bd43d1216a)
   and record a baseline from it.
2. Build the commit right before the fix (`cf05b37`) and run the same golden set against
   that baseline. That's equivalent to the bug being reintroduced.

The two fixture files come from the tests added in the fix commit, so this reproduces a
known bug. It is not a newly found one.

## Run it

```bash
./reproduce.sh
```

Needs `git`, `node`/`npm` and [`uv`](https://docs.astral.sh/uv/). It clones the upstream repo
into `work/` (ignored by git), builds both commits, generates the fixtures and golden
sets (`generate_golden.py`), and runs the gate twice. About a minute.

## Real output

`run.log` is the unedited output of `./reproduce.sh`; `baseline.json` is what step 1 wrote.

```
== 1. baseline on the FIXED commit
│ head-utf8-boundary │  1.00 │ PASS   │ exact match │
│ tail-utf8-boundary │  1.00 │ PASS   │ exact match │

== 2. gate on the commit just BEFORE the fix, same baseline
│ head-utf8-boundary │  0.00 │ FAIL (regression) │ first difference at char 1023 (expected 1024 chars, got 1026): │
│                    │       │                   │ expected '…aaaaaaaaaaaaaaaaaaaa界', got '…aaaaaaaaaaaaaaaaaaaa���' │
│ tail-utf8-boundary │  0.00 │ FAIL (regression) │ first difference at char 0 (expected 1023 chars, got 1025): │
│                    │       │                   │ expected '界aaaaaaaaaaaaaaaaaaa…', got '���aaaaaaaaaaaaaaaaa…' │

gate exit code: 1
```

## What running against a real bug taught us

The first version of this run printed the full expected and actual strings in the failure
detail, about 2,000 characters of `a` per case, which made the report unreadable. The
planted `42` vs `43` regression in validation 1 never showed that. Failure details now
point at the first differing character with short context, as above.

## Limits

- One bug, one server. It shows the gate catches a real output regression end to end, not
  how often that class of bug occurs. In the upstream issue tracker, schema and conformance
  bugs were more common than output-value bugs, and this tool does not check schemas.
- Exact matching is enough here because the output is deterministic. Tools whose output
  varies between runs (timestamps, ids, search rankings) need normalization or looser
  matching, which this tool does not have yet.
