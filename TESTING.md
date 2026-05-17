# Testing

## Unit tests

Fast, no network, no LLM:

```bash
uv run pytest tests/unit -q
```

## Integration

Pipeline tests mock the LLM (`tests/integration/conftest.py` + `tests/fake_llm.py`):

```bash
uv run pytest tests/integration -q
```

## Build schema index first

```bash
uv run python scripts/build_schema_index.py
```

## Coverage

```bash
uv run pytest --cov=case3 --cov-report=term-missing
```
