"""Parse GreenData DDL dump into SchemaIndex."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    data_type: str = ""
    comment: str = ""
    sensitive: bool = False


class TableInfo(BaseModel):
    name: str
    comment: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class SchemaIndex(BaseModel):
    tables: dict[str, TableInfo] = Field(default_factory=dict)
    fk_edges: list[tuple[str, str, str, str]] = Field(
        default_factory=list,
        description="(from_table, from_col, to_table, to_col)",
    )


_CREATE_TABLE = re.compile(
    r"CREATE TABLE\s+(?:public\.)?(\w+)\s*\((.*?)\);",
    re.DOTALL | re.IGNORECASE,
)
_COMMENT_TABLE = re.compile(
    r"COMMENT ON TABLE\s+public\.(\w+)\s+IS\s+'((?:[^']|'')*)'",
    re.IGNORECASE,
)
_COMMENT_COLUMN = re.compile(
    r"COMMENT ON COLUMN\s+public\.(\w+)\.(\w+)\s+IS\s+'((?:[^']|'')*)'",
    re.IGNORECASE,
)
_FK_REF = re.compile(
    r"FOREIGN KEY\s*\((\w+)\)\s+REFERENCES\s+public\.(\w+)\((\w+)\)",
    re.IGNORECASE,
)
_COLUMN_LINE = re.compile(r"^\s*(\w+)\s+([\w\s().,]+?)(?:,|\s*$)", re.IGNORECASE)


def _unescape_comment(s: str) -> str:
    return s.replace("''", "'")


def parse_ddl(text: str) -> SchemaIndex:
    tables: dict[str, TableInfo] = {}
    fk_edges: list[tuple[str, str, str, str]] = []

    for m in _CREATE_TABLE.finditer(text):
        table_name = m.group(1)
        body = m.group(2)
        cols: list[ColumnInfo] = []
        for line in body.splitlines():
            line = line.strip()
            if not line or line.upper().startswith("CONSTRAINT"):
                continue
            cm = _COLUMN_LINE.match(line)
            if cm:
                cols.append(ColumnInfo(name=cm.group(1), data_type=cm.group(2).strip().rstrip(",")))
        tables[table_name] = TableInfo(name=table_name, columns=cols)

    for m in _COMMENT_TABLE.finditer(text):
        tname = m.group(1)
        if tname not in tables:
            tables[tname] = TableInfo(name=tname)
        tables[tname].comment = _unescape_comment(m.group(2))

    for m in _COMMENT_COLUMN.finditer(text):
        tname, cname, comment = m.group(1), m.group(2), _unescape_comment(m.group(3))
        if tname not in tables:
            tables[tname] = TableInfo(name=tname)
        table = tables[tname]
        col = next((c for c in table.columns if c.name == cname), None)
        if col is None:
            table.columns.append(ColumnInfo(name=cname, comment=comment))
        else:
            col.comment = comment

    # FKs appear in active and commented ALTER blocks. Many reference tables
    # that aren't included in this DDL slice — we keep only edges between
    # known tables so the FK graph stays useful for retrieval.
    known = set(tables.keys())
    seen: set[tuple[str, str, str, str]] = set()
    for m in _FK_REF.finditer(text):
        from_col, to_table, to_col = m.group(1), m.group(2), m.group(3)
        if to_table not in known:
            continue
        start = max(0, m.start() - 500)
        chunk = text[start : m.start()]
        tm = re.search(r"ALTER\s+TABLE(?:\s+ONLY)?\s+public\.(\w+)", chunk, re.IGNORECASE)
        if not tm:
            continue
        from_table = tm.group(1)
        if from_table not in known or from_table == to_table:
            continue
        key = (from_table, from_col, to_table, to_col)
        if key in seen:
            continue
        seen.add(key)
        fk_edges.append(key)

    return SchemaIndex(tables=tables, fk_edges=fk_edges)


def build_schema_index(ddl_path: Path) -> SchemaIndex:
    text = ddl_path.read_text(encoding="utf-8", errors="replace")
    index = parse_ddl(text)
    from case3.schema_index.graph import enrich_fk_edges
    from case3.schema_index.pii import mark_sensitive_columns

    index.fk_edges = enrich_fk_edges(index)
    mark_sensitive_columns(index)
    return index
