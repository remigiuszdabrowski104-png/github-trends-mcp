# Contributing

Thanks for your interest in improving github-trends-mcp.

## Development setup

```bash
git clone https://github.com/remigiuszdabrowski104-png/github-trends-mcp.git
cd github-trends-mcp
uv sync
```

## Running tests

```bash
uv run pytest
```

All tests must pass and use mocked HTTP — please do not add tests that hit the live GitHub API.

## Pull requests

1. Open an issue first for non-trivial changes.
2. Keep commits focused and use clear messages (e.g. `fix:`, `feat:`, `docs:`, `chore:`).
3. Add or update tests for any behavior change.
4. Make sure `uv run pytest` is green before opening the PR.

## Code style

- Python 3.13, type hints where practical.
- Keep docstrings and comments in English.
