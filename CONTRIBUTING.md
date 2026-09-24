# Contributing

## Workflow

- `main` is always green. Work happens on short-lived branches named `<type>/<description>`
  (for example `feat/normalizers`), merged through a pull request once CI passes.
- Merge with a merge commit so each commit on the branch stays visible in history.
- Commit messages: `<type>: <description>`, with type one of
  `feat|fix|refactor|docs|test|chore|perf|ci`.

## Versioning

[SemVer](https://semver.org/). Before 1.0, a breaking change to the golden-set schema or the
CLI/MCP tool signatures bumps the minor version. Releases are annotated tags (`vX.Y.Z`) with
a section in `CHANGELOG.md`.

## Local development

```bash
uv sync --extra judge --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests && uv run ruff format src tests
```
