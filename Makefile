.PHONY: check build-schema eval db-up db-down db-seed db-reset presentation-pdf

build-schema:
	uv run python scripts/build_schema_index.py

eval:
	uv run python scripts/eval.py

db-up:
	docker compose up -d
	@until docker compose exec -T postgres pg_isready -U case3 -d demo_db >/dev/null 2>&1; do sleep 1; done

db-down:
	docker compose down

db-seed: db-up
	uv run python scripts/seed_db.py

db-reset:
	docker compose down -v
	$(MAKE) db-seed

check: build-schema
	uv run ruff format .
	uv run ruff check . --fix
	uv run mypy .
	uv run pytest

presentation-pdf:
	pandoc presentation.md --slide-level=2 -t beamer -o presentation.pdf \
		--pdf-engine=xelatex \
		-V mainfont="Helvetica Neue" \
		-V monofont="Menlo"

