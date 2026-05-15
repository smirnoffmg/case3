"""BM25 retrieval over schema tables for RAG context."""

from __future__ import annotations

from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from case3.schema_index.parser import SchemaIndex, TableInfo


class TableContext(BaseModel):
    name: str
    comment: str
    columns_text: str
    score: float = 0.0


def _table_document(table: TableInfo) -> str:
    parts = [table.name, table.comment]
    for col in table.columns:
        parts.append(f"{col.name} {col.data_type} {col.comment}")
        if col.sensitive:
            parts.append("SENSITIVE")
    return " ".join(parts)


class SchemaRetriever:
    def __init__(self, index: SchemaIndex) -> None:
        self._index = index
        self._names = list(index.tables.keys())
        self._docs = [_table_document(index.tables[n]) for n in self._names]
        tokenized = [d.lower().split() for d in self._docs]
        self._bm25 = BM25Okapi(tokenized)

    def retrieve(self, task: str, top_k: int = 8) -> list[TableContext]:
        if not self._names:
            return []
        scores = self._bm25.get_scores(task.lower().split())
        ranked = sorted(
            zip(self._names, scores, strict=True),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]
        out: list[TableContext] = []
        for name, score in ranked:
            if score <= 0 and out:
                break
            t = self._index.tables[name]
            cols = ", ".join(
                f"{c.name} ({c.data_type})" + (" [PII]" if c.sensitive else "")
                for c in t.columns[:30]
            )
            out.append(
                TableContext(
                    name=name,
                    comment=t.comment,
                    columns_text=cols,
                    score=float(score),
                )
            )
        return out or self._fallback(top_k)

    def _fallback(self, top_k: int) -> list[TableContext]:
        names = self._names[:top_k]
        return [
            TableContext(
                name=n,
                comment=self._index.tables[n].comment,
                columns_text=", ".join(c.name for c in self._index.tables[n].columns[:20]),
            )
            for n in names
        ]
