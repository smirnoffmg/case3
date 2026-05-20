"""Optional postgres backend for true Execution Accuracy.

When `EVAL_DATABASE_URL` is set (or `--db` is passed) the eval runner can
execute both pred and gold SQL against a real database (the dockerized
demo_db with seed data) and compare result sets instead of falling back to
AST string match.

The DB is wrapped in a `READ ONLY` transaction with a 5s statement timeout,
so a buggy generated query can't lock or mutate anything.
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)


def strip_limit(sql: str) -> str:
    """Remove LIMIT (and OFFSET) clauses for set-level comparison.

    Gold queries often pin LIMIT to an arbitrary value (20, 50, ...) that the
    user task never mentioned — penalising a generator for choosing a different
    pagination size masks whether the semantic query (SELECT/WHERE/JOIN/GROUP)
    is right. Strip LIMIT before comparing result sets and rely on
    NO_PAGINATION audit detection for the safety side.
    """
    if not sql:
        return sql
    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except sqlglot.errors.ParseError:
        return re.sub(r"\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?", "", sql, flags=re.I)
    for limit_node in list(parsed.find_all(exp.Limit)):
        limit_node.pop()
    for offset_node in list(parsed.find_all(exp.Offset)):
        offset_node.pop()
    return parsed.sql(dialect="postgres")


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
        with contextlib.suppress(Exception):
            self._conn.close()

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
            with contextlib.suppress(Exception):
                cur.execute("ROLLBACK")
            raise
        finally:
            cur.close()

    def fetch(self, sql: str) -> tuple[list[str], Sequence[tuple[Any, ...]]] | None:
        """Run `sql`; return (column_names, rows), or None if it didn't execute."""
        if not sql or sql.strip().startswith("--"):
            return None
        try:
            with self._readonly_tx() as cur:
                cur.execute(sql)
                cols = [d.name for d in (cur.description or [])]
                return cols, list(cur.fetchall())
        except Exception as exc:
            logger.debug("EvalDB.fetch failed: %s | sql=%s", exc, sql.replace("\n", " ")[:200])
            return None


def _canonical_rows(rows: Sequence[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    """Make rows comparable: stringify cells (Decimal, datetime, etc.), sort."""
    out = [tuple("" if c is None else str(c) for c in r) for r in rows]
    out.sort()
    return out


def _project(rows: Sequence[tuple[Any, ...]], idx: list[int]) -> list[tuple[Any, ...]]:
    return [tuple(r[i] for i in idx) for r in rows]


def _id_set(cols: list[str], rows: Sequence[tuple[Any, ...]]) -> set[str] | None:
    """Extract the set of ``id`` values; None if ``id`` column not present."""
    cols_lc = [c.lower() for c in cols]
    if "id" not in cols_lc:
        return None
    i = cols_lc.index("id")
    return {("" if r[i] is None else str(r[i])) for r in rows}


def result_sets_equal(
    pred: tuple[list[str], Sequence[tuple[Any, ...]]] | None,
    gold: tuple[list[str], Sequence[tuple[Any, ...]]] | None,
) -> bool:
    """True if both sides ran and produced semantically equivalent output.

    Comparison strategy:

    1. **PK match** — when both sides include an ``id`` column, compare the
       set of returned ids. Robust to extra/localised columns: the question
       "did the query select the right rows?" is answered by the row set.
    2. **Tuple match** — for aggregates / non-id projections, compare as a
       canonicalised multiset of tuples. Pred's columns may be a superset of
       gold's (gold projected away before comparison).
    """
    if pred is None or gold is None:
        return False
    pred_cols, pred_rows = pred
    gold_cols, gold_rows = gold

    # PK-based: works for the dominant case of "list of rows" tasks.
    pred_ids = _id_set(pred_cols, pred_rows)
    gold_ids = _id_set(gold_cols, gold_rows)
    if pred_ids is not None and gold_ids is not None:
        return pred_ids == gold_ids

    # Single-cell aggregate equivalence (e.g. MIN(id) vs ORDER BY id LIMIT 1).
    if (
        len(pred_rows) == 1
        and len(gold_rows) == 1
        and len(pred_rows[0]) == 1
        and len(gold_rows[0]) == 1
    ):
        p = pred_rows[0][0]
        g = gold_rows[0][0]
        return ("" if p is None else str(p)) == ("" if g is None else str(g))

    # Single-column projection equivalence (DISTINCT type_id, names, etc.):
    # compare value multisets across the only column on each side.
    if len(pred_cols) == 1 and len(gold_cols) == 1:
        p_set = {("" if r[0] is None else str(r[0])) for r in pred_rows}
        g_set = {("" if r[0] is None else str(r[0])) for r in gold_rows}
        return p_set == g_set

    if not pred_cols or not gold_cols:
        return _canonical_rows(pred_rows) == _canonical_rows(gold_rows)
    pred_cols_lc = [c.lower() for c in pred_cols]
    gold_cols_lc = [c.lower() for c in gold_cols]
    if all(c in pred_cols_lc for c in gold_cols_lc):
        idx = [pred_cols_lc.index(c) for c in gold_cols_lc]
        return _canonical_rows(_project(pred_rows, idx)) == _canonical_rows(gold_rows)
    return _canonical_rows(pred_rows) == _canonical_rows(gold_rows)
