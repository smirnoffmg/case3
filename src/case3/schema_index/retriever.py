"""BM25 retrieval over schema tables for RAG context."""

from __future__ import annotations

import re

import pymorphy3
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from case3.schema_index.parser import SchemaIndex, TableInfo

_morph: pymorphy3.MorphAnalyzer | None = None


def _get_morph() -> pymorphy3.MorphAnalyzer:
    global _morph
    if _morph is None:
        _morph = pymorphy3.MorphAnalyzer()
    return _morph


_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
_BOILERPLATE = re.compile(r",?\s*(?:Sys|Abstract)\w*\{[^}]*\}")
_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")

# Prepositions and conjunctions that are never meaningful schema terms.
_STOPWORDS = frozenset(
    {
        "по", "с", "в", "из", "для", "и", "или", "без", "к", "на", "за",
        "от", "об", "не", "но", "а", "да", "это", "уже", "при", "до",
    }
)


def _clean_comment(s: str) -> str:
    """Strip SysObjTypeEffective / AbstractAttrEffective metadata from comments."""
    return _BOILERPLATE.sub("", s).strip().strip(",").strip()


def _lemmatize(token: str) -> str:
    """Lemmatize Cyrillic tokens; strip common English plurals; pass rest through."""
    if _CYRILLIC.search(token):
        parsed = _get_morph().parse(token)
        if parsed:
            return parsed[0].normal_form
    # Light English desinflection: strip trailing -s (not -es) so "employees" → "employee"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """Split on non-letter boundaries, lemmatize, drop stopwords."""
    return [
        lemma
        for raw in _TOKEN_RE.findall(text.lower())
        if (lemma := _lemmatize(raw)) not in _STOPWORDS
    ]


def _split_identifier(ident: str) -> str:
    """Return original identifier plus its underscore-split parts as extra tokens."""
    parts = [p for p in ident.split("_") if p]
    if len(parts) > 1:
        return ident + " " + " ".join(parts)
    return ident


def _table_document(table: TableInfo) -> str:
    clean_name = _split_identifier(table.name)
    clean_comment = _clean_comment(table.comment)
    # BM25 document contains only table identity (name + comment), repeated 3×.
    # Column names and comments are excluded: with 50+ columns per table, they
    # dominate document length and skew BM25 length-normalization against large tables.
    # The LLM receives full column lists separately via TableContext.columns_text.
    return " ".join([clean_name, clean_comment] * 3)


def _build_fk_adjacency(index: SchemaIndex) -> dict[str, set[str]]:
    """Undirected adjacency: both FK source and target directions."""
    adj: dict[str, set[str]] = {name: set() for name in index.tables}
    for from_table, _, to_table, _ in index.fk_edges:
        if from_table in adj and to_table in adj:
            adj[from_table].add(to_table)
            adj[to_table].add(from_table)
    return adj


class TableContext(BaseModel):
    name: str
    comment: str
    columns_text: str
    score: float = 0.0


class SchemaRetriever:
    _MIN_SCORE = 0.5  # below this, BM25 result is noise — use fallback
    _FK_BUDGET = 3  # max FK-expanded tables appended after BM25 results

    def __init__(self, index: SchemaIndex) -> None:
        self._index = index
        self._names = list(index.tables.keys())
        self._docs = [_table_document(index.tables[n]) for n in self._names]
        tokenized = [_tokenize(d) for d in self._docs]
        self._bm25 = BM25Okapi(tokenized)
        self._fk_adj = _build_fk_adjacency(index)

    def retrieve(self, task: str, top_k: int = 8) -> list[TableContext]:
        if not self._names:
            return []
        scores = self._bm25.get_scores(_tokenize(task))
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
            out.append(self._make_context(name, float(score)))

        out = out or self._fallback(top_k)
        return self._expand_fk(out)

    def _make_context(self, name: str, score: float = 0.0) -> TableContext:
        t = self._index.tables[name]
        cols = ", ".join(
            f"{c.name} ({c.data_type})" + (" [PII]" if c.sensitive else "")
            for c in t.columns[:30]
        )
        return TableContext(
            name=name,
            comment=_clean_comment(t.comment),
            columns_text=cols,
            score=score,
        )

    def _expand_fk(self, bm25_results: list[TableContext]) -> list[TableContext]:
        present = {t.name for t in bm25_results}
        additions: list[TableContext] = []
        for hit in bm25_results:
            for neighbor in self._fk_adj.get(hit.name, set()):
                if neighbor in present or len(additions) >= self._FK_BUDGET:
                    continue
                additions.append(self._make_context(neighbor))
                present.add(neighbor)
        return bm25_results + additions

    def _fallback(self, top_k: int) -> list[TableContext]:
        return [self._make_context(n) for n in self._names[:top_k]]
