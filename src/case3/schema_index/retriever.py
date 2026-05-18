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


def _split_identifier(ident: str) -> str:
    """Return original identifier plus its underscore-split parts as extra tokens."""
    parts = [p for p in ident.split("_") if p]
    if len(parts) > 1:
        return ident + " " + " ".join(parts)
    return ident


def _table_document(table: TableInfo) -> str:
    parts = [_split_identifier(table.name), table.comment]
    for col in table.columns:
        parts.append(f"{_split_identifier(col.name)} {col.data_type} {col.comment}")
        if col.sensitive:
            parts.append("SENSITIVE")
    return " ".join(parts)


def _build_fk_adjacency(index: SchemaIndex) -> dict[str, set[str]]:
    """Undirected adjacency: both FK source and target directions."""
    adj: dict[str, set[str]] = {name: set() for name in index.tables}
    for from_table, _, to_table, _ in index.fk_edges:
        if from_table in adj and to_table in adj:
            adj[from_table].add(to_table)
            adj[to_table].add(from_table)
    return adj


class SchemaRetriever:
    _MIN_SCORE = 0.5  # below this, BM25 result is noise — use fallback
    _FK_BUDGET = 3  # max FK-expanded tables appended after BM25 results

    def __init__(self, index: SchemaIndex) -> None:
        self._index = index
        self._names = list(index.tables.keys())
        self._docs = [_table_document(index.tables[n]) for n in self._names]
        tokenized = [d.lower().split() for d in self._docs]
        self._bm25 = BM25Okapi(tokenized)
        self._fk_adj = _build_fk_adjacency(index)

    def retrieve(self, task: str, top_k: int = 8) -> list[TableContext]:
        if not self._names:
            return []
        scores = self._bm25.get_scores(task.lower().split())
        if max(scores) < self._MIN_SCORE:
            return self._expand_fk(self._fallback(top_k))
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
                TableContext(name=name, comment=t.comment, columns_text=cols, score=float(score))
            )

        out = out or self._fallback(top_k)
        return self._expand_fk(out)

    def _expand_fk(self, bm25_results: list[TableContext]) -> list[TableContext]:
        present = {t.name for t in bm25_results}
        additions: list[TableContext] = []
        for hit in bm25_results:
            for neighbor in self._fk_adj.get(hit.name, set()):
                if neighbor in present or len(additions) >= self._FK_BUDGET:
                    continue
                t = self._index.tables[neighbor]
                cols = ", ".join(
                    f"{c.name} ({c.data_type})" + (" [PII]" if c.sensitive else "")
                    for c in t.columns[:30]
                )
                additions.append(
                    TableContext(name=neighbor, comment=t.comment, columns_text=cols, score=0.0)
                )
                present.add(neighbor)
        return bm25_results + additions

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
