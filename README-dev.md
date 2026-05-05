## Dev (uv + ruff + mypy)

### Setup

```bash
uv sync --dev
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

