.PHONY: check build-schema eval

build-schema:
	uv run python scripts/build_schema_index.py

eval:
	uv run python scripts/eval.py

check: build-schema
	uv run ruff format .
	uv run ruff check . --fix
	uv run mypy .
	uv run pytest

