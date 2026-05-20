"""Validate every gold SQL in a dataset against the dockerized postgres.

Substitutes template placeholders ({number}, {date}, {name}, {from}, {to})
with sensible defaults before execution, runs each query in a READ ONLY
tx with a 5s statement timeout, and prints a classified report.

Usage:
    EVAL_DATABASE_URL=postgresql://case3:case3@localhost:55432/demo_db \
      uv run python scripts/validate_dataset.py data/dataset/tasks_v2.jsonl
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg

DEFAULT_DSN = "postgresql://case3:case3@localhost:55432/demo_db"

_PLACEHOLDERS: dict[str, str] = {
    "{number}": "100",
    "{date}": "2020-01-01",
    "{name}": "Test",
    "{from}": "0",
    "{to}": "1000",
}


def substitute(sql: str) -> str:
    out = sql
    for k, v in _PLACEHOLDERS.items():
        out = out.replace(k, v)
    return out


def validate(path: Path, dsn: str) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(rows)} rows from {path}")

    ok = 0
    failures: list[tuple[int, str, str, str]] = []
    empty_rowsets: list[tuple[int, str]] = []
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 5000")
        for i, row in enumerate(rows, start=1):
            task = row["task"]
            sql = substitute(row["sql"])
            try:
                cur.execute("BEGIN READ ONLY")
                cur.execute(sql)
                result = cur.fetchall()
                cur.execute("ROLLBACK")
                ok += 1
                if not result:
                    empty_rowsets.append((i, task))
            except Exception as exc:  # noqa: BLE001
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                short = " ".join(str(exc).split())[:160]
                failures.append((i, task, sql, short))

    print(f"\nOK: {ok}/{len(rows)}")
    print(f"Empty result set (table likely unseeded): {len(empty_rowsets)}")
    print(f"Errors: {len(failures)}")

    if failures:
        print("\n--- Failures ---")
        for i, task, sql, err in failures:
            print(f"[{i:>2}] {task[:70]}")
            print(f"     SQL: {sql[:140]}")
            print(f"     ERR: {err}")
    if empty_rowsets:
        print("\n--- Empty result sets (first 15) ---")
        for i, task in empty_rowsets[:15]:
            print(f"[{i:>2}] {task[:90]}")
        if len(empty_rowsets) > 15:
            print(f"... and {len(empty_rowsets) - 15} more")
    return 0 if not failures else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: validate_dataset.py <path/to/tasks.jsonl>", file=sys.stderr)
        sys.exit(2)
    dsn = os.environ.get("EVAL_DATABASE_URL", DEFAULT_DSN)
    sys.exit(validate(Path(sys.argv[1]), dsn))
