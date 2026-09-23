# Contributing

## Branching model

Trunk-based, GitHub-flow style — no long-lived `develop` branch:

- `main` is always releasable; every commit on it has passed CI.
- Work happens on short-lived branches off `main`, named `<type>/<short-description>`,
  matching the commit types below (e.g. `feat/retrieval-scoring`, `fix/doc-id-fallback`).
- Open a PR into `main`. CI (lint + tests + coverage gate + build) must pass.
- Merge with a merge commit (not squash) so the logical commit sequence on the branch
  stays visible in `main`'s history — each commit should be a coherent, reviewable unit.
- Delete the branch after merge.

## Commits

Conventional Commits: `<type>: <description>`, types `feat|fix|refactor|docs|test|chore|perf|ci`.

## Releasing

1. Update `version` in `pyproject.toml` and add a section to `CHANGELOG.md`.
2. Commit: `chore(release): vX.Y.Z`.
3. Merge to `main`, then tag: `git tag -a vX.Y.Z -m "vX.Y.Z"` and `git push origin vX.Y.Z`.
4. Create a GitHub Release from the tag (`gh release create vX.Y.Z --generate-notes`).
5. Publishing to PyPI/npm is a separate, explicit step — not automated yet.

Versioning follows [SemVer](https://semver.org/): breaking changes to the golden-set
schema or CLI/MCP tool signatures bump the major version while pre-1.0.

## Local dev

```bash
uv sync --extra mcp --dev
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check src tests && uv run ruff format src tests
```
