"""Writes the two fixture files and the two golden sets used by reproduce.sh.

The fixtures are taken from the tests added in the real fix commit
(modelcontextprotocol/servers#4667): a multi-byte character placed so it
straddles the 1024-byte chunk boundary used by read_text_file's head/tail.
"""

import sys
from pathlib import Path

import yaml

work = Path(sys.argv[1]).resolve()
data = work / "data"
data.mkdir(exist_ok=True)

(data / "head.txt").write_bytes(b"a" * 1023 + "界\nsecond".encode())
(data / "tail.txt").write_bytes(b"discard\n" + "界".encode() + b"a" * 1017 + b"\nlast")

cases = [
    {
        "id": "head-utf8-boundary",
        "tool_name": "read_text_file",
        "tool_args": {"path": str(data / "head.txt"), "head": 1},
        "match_type": "exact",
        "expected_output": "a" * 1023 + "界",
    },
    {
        "id": "tail-utf8-boundary",
        "tool_name": "read_text_file",
        "tool_args": {"path": str(data / "tail.txt"), "tail": 2},
        "match_type": "exact",
        "expected_output": "界" + "a" * 1017 + "\nlast",
    },
]

for name in ("fixed", "prefix"):
    server_js = work / name / "src" / "filesystem" / "dist" / "index.js"
    config = {"server": {"command": "node", "args": [str(server_js), str(data)]}, "cases": cases}
    (work / f"golden_{name}.yaml").write_text(yaml.safe_dump(config, allow_unicode=True, width=10**6))

print(f"wrote fixtures and golden sets in {work}")
