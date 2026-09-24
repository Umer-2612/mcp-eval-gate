#!/usr/bin/env bash
# Reproduces validation #2: the gate catching a real, known bug in a real MCP server.
# Needs: git, node/npm, and uv (or set GATE and PY yourself). Free, no API keys.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="$HERE/work"
FIX=11845d51cbb42cba9695566f9134f5bd43d1216a # modelcontextprotocol/servers#4667

GATE=(uv run --project "$REPO" mcp-eval-gate)
PY=(uv run --project "$REPO" python)

mkdir -p "$WORK"
cd "$WORK"
[ -d servers ] || git clone -q --filter=blob:none https://github.com/modelcontextprotocol/servers.git
(cd servers && { [ -d ../fixed ] || git worktree add -q ../fixed "$FIX"; } \
            && { [ -d ../prefix ] || git worktree add -q ../prefix "$FIX^"; })

for v in fixed prefix; do
  echo "== building $v: $(git -C "$v" log --oneline -1)"
  (cd "$v/src/filesystem" && npm ci >/dev/null 2>&1 && npm run build >/dev/null 2>&1)
done

"${PY[@]}" "$HERE/generate_golden.py" "$WORK"

echo; echo "== 1. baseline on the FIXED commit"
"${GATE[@]}" run --config golden_fixed.yaml --baseline baseline.json --update-baseline 2>&1 | grep -v "npm warn"

echo; echo "== 2. gate on the commit just BEFORE the fix, same baseline"
set +e
COLUMNS=120 "${GATE[@]}" run --config golden_prefix.yaml --baseline baseline.json 2>&1 | grep -v "npm warn"
code=${PIPESTATUS[0]}
set -e
echo; echo "gate exit code: $code (expected 1)"
