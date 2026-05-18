"""Load/save schema index and convert to baseline db_schema dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from case3.schema_index.parser import SchemaIndex, build_schema_index


def load_schema_index(path: Path) -> SchemaIndex:
    if path.is_file():
        return SchemaIndex.model_validate_json(path.read_text(encoding="utf-8"))
    settings_ddl = path.parent.parent / "schema" / "data_model.sql"
    if settings_ddl.is_file():
        return build_schema_index(settings_ddl)
    msg = f"Schema index not found: {path}"
    raise FileNotFoundError(msg)


def save_schema_index(index: SchemaIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2), encoding="utf-8")


def to_baseline_dict(index: SchemaIndex) -> dict[str, Any]:
    """Format for SecurityAuditor.db_schema / SQLGenerator.db_schema."""
    tables: dict[str, Any] = {}
    sensitive: set[str] = set()
    for name, table in index.tables.items():
        cols = []
        for c in table.columns:
            entry: dict[str, Any] = {
                "name": c.name,
                "type": c.data_type,
                "comment": c.comment,
            }
            if c.sensitive:
                entry["sensitive"] = True
                sensitive.add(f"{name}.{c.name}")
            cols.append(entry)
        tables[name] = {"comment": table.comment, "columns": cols}
    return {
        "tables": tables,
        "sensitive_columns": sorted(sensitive),
        "fk_edges": [
            {"from_table": a, "from_col": b, "to_table": c, "to_col": d}
            for a, b, c, d in index.fk_edges
        ],
    }


def sensitive_column_set_from_index(index: SchemaIndex) -> set[str]:
    return {
        f"{name}.{col.name}"
        for name, table in index.tables.items()
        for col in table.columns
        if col.sensitive
    }
