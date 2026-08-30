# Contributing Guide

## Development environment

Use Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

Before making changes, update `develop` to the latest and create a working branch. Pull requests should be merged into `develop`.

## Quality checks

Before creating a pull request, run all of the following commands.

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

Anything Ruff can auto-fix can be fixed with the following.

```bash
uv run ruff check src tests --fix
uv run ruff format src tests
```

Add tests for new behavior, and update the README and configuration examples for changes affecting users. Do not commit local GGUF models, logs, or generated reports.

## Commits and pull requests

Use Conventional Commits. The format is `type(scope): description`.

```text
feat(collection): add source filter
fix(report): preserve source name
docs(readme): clarify setup
```

Include the purpose, changes made, verification commands run, and any impact on configuration or compatibility in the pull request.

## Security issues

Do not report vulnerabilities in public issues; follow the procedure in [SECURITY.md](SECURITY.md).