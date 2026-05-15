## Dev (uv + ruff + mypy)

### Setup

```bash
uv sync --dev
uv run python scripts/build_schema_index.py
```

### Tests

```bash
uv run pytest
```

### Lint / format

```bash
uv run ruff check .
uv run ruff format .
```

### Types

```bash
uv run mypy .
```

### All checks

```bash
make check
```
