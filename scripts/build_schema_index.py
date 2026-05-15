#!/usr/bin/env python3
"""Build data/derived/schema.json from DDL."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from case3.config import get_settings
from case3.schema_index.loader import save_schema_index
from case3.schema_index.parser import build_schema_index


def main() -> None:
    settings = get_settings()
    ddl = settings.schema_ddl_path
    if not ddl.is_file():
        msg = f"DDL not found: {ddl}"
        raise SystemExit(msg)
    index = build_schema_index(ddl)
    save_schema_index(index, settings.schema_json_path)
    print(f"Wrote {len(index.tables)} tables -> {settings.schema_json_path}")


if __name__ == "__main__":
    main()
