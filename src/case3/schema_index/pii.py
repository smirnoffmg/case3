"""Mark sensitive columns from YAML + name heuristics."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from case3.config import get_settings
from case3.schema_index.parser import SchemaIndex

_DEFAULT_PATTERNS = [
    r"password",
    r"passwd",
    r"token",
    r"secret",
    r"ssn",
    r"card",
    r"email",
    r"phone",
    r"birthday",
    r"birth_date",
    r"passport",
    r"inn",
    r"snils",
]


def load_sensitivity_patterns(path: Path | None = None) -> list[re.Pattern[str]]:
    path = path or get_settings().sensitivity_path
    patterns = list(_DEFAULT_PATTERNS)
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        patterns.extend(data.get("column_patterns", []))
        for col in data.get("columns", []):
            patterns.append(re.escape(str(col)))
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def mark_sensitive_columns(
    index: SchemaIndex,
    patterns: list[re.Pattern[str]] | None = None,
) -> None:
    patterns = patterns or load_sensitivity_patterns()
    for table in index.tables.values():
        for col in table.columns:
            text = f"{table.name}.{col.name}"
            col.sensitive = any(p.search(text) or p.search(col.name) for p in patterns)
