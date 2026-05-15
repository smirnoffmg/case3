# Testing

## Unit tests

Fast, no network, stub LLM by default:

```bash
uv run pytest tests/unit -q
```

## Integration

Full pipeline with stub LLM:

```bash
uv run pytest tests/integration -q
```

## Build schema index first

Parser tests use fixtures; integration expects `data/derived/schema.json`:

```bash
uv run python scripts/build_schema_index.py
```

## Coverage

```bash
uv run pytest --cov=case3 --cov-report=term-missing
```
