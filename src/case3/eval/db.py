"""Optional postgres backend for true Execution Accuracy.

When `EVAL_DATABASE_URL` is set (or `--db` is passed) the eval runner can
execute both pred and gold SQL against a real database (the dockerized
demo_db with seed data) and compare result sets instead of falling back to
AST string match.

The DB is wrapped in a `READ ONLY` transaction with a 5s statement timeout,
so a buggy generated query can't lock or mutate anything.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


def _try_import_psycopg() -> Any:
    try:
        import psycopg

        return psycopg
    except ImportError:
        return None


class EvalDB:
    """Connection holder for offline Execution-Accuracy checks."""

    def __init__(self, dsn: str, statement_timeout_ms: int = 5000) -> None:
        self._dsn = dsn
        self._statement_timeout_ms = statement_timeout_ms
        self._psycopg = _try_import_psycopg()
        if self._psycopg is None:
            raise RuntimeError("psycopg is not installed; cannot run DB-backed eval")
        self._conn = self._psycopg.connect(dsn, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(statement_timeout_ms)}")

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    @contextmanager
    def _readonly_tx(self) -> Any:
        # Wrap each query in a fresh READ-ONLY tx so even DML/DDL the
        # generator might emit gets rejected by postgres itself.
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN READ ONLY")
            yield cur
            cur.execute("ROLLBACK")
        except Exception:
            try:
                cur.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            cur.close()

    def fetch(self, sql: str) -> Sequence[tuple[Any, ...]] | None:
        """Run `sql`; return result rows, or None if it didn't execute."""
        if not sql or sql.strip().startswith("--"):
            return None
        try:
            with self._readonly_tx() as cur:
                cur.execute(sql)
                return list(cur.fetchall())
        except Exception as exc:  # noqa: BLE001 — catch broad DB errors
            logger.debug("EvalDB.fetch failed: %s | sql=%s", exc, sql.replace("\n", " ")[:200])
            return None


def _canonical_rows(rows: Sequence[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Make rows comparable: stringify cells (Decimal, datetime, etc.), sort."""
    out = [tuple("" if c is None else str(c) for c in r) for r in rows]
    out.sort()
    return out


def result_sets_equal(
    pred_rows: Sequence[tuple[Any, ...]] | None,
    gold_rows: Sequence[tuple[Any, ...]] | None,
) -> bool:
    """True if both sides ran and produced the same canonicalised multiset."""
    if pred_rows is None or gold_rows is None:
        return False
    return _canonical_rows(pred_rows) == _canonical_rows(gold_rows)
