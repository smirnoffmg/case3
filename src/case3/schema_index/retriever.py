from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from case3.models import TableInfo


class SchemaRetriever(Protocol):
    def retrieve(self, task: str, *, k: int) -> list[TableInfo]: ...


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _table_document(table: TableInfo) -> str:
    cols = " ".join(c.name for c in table.columns)
    return f"{table.name} {cols}"


class Bm25SchemaRetriever:
    def __init__(self, tables: Iterable[TableInfo]):
        self._tables = list(tables)
        docs = [_table_document(t) for t in self._tables]
        self._tokenized_docs = [_tokenize(d) for d in docs]
        self._bm25 = BM25Okapi(self._tokenized_docs)

    def retrieve(self, task: str, *, k: int) -> list[TableInfo]:
        if k <= 0 or not self._tables:
            return []
        query = _tokenize(task)
        scores = self._bm25.get_scores(query)
        ranked = sorted(range(len(self._tables)), key=lambda i: scores[i], reverse=True)
        top = ranked[: min(k, len(ranked))]
        return [self._tables[i] for i in top]
