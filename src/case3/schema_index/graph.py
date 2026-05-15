"""FK graph: explicit REFERENCES + heuristic _id columns."""

from __future__ import annotations

import re

from case3.schema_index.parser import SchemaIndex

_ID_SUFFIX = re.compile(r"^(.+)_id$", re.IGNORECASE)


def enrich_fk_edges(index: SchemaIndex) -> list[tuple[str, str, str, str]]:
    edges = list(index.fk_edges)
    seen = {(a, b, c, d) for a, b, c, d in edges}
    table_names = set(index.tables.keys())

    for tname, table in index.tables.items():
        for col in table.columns:
            m = _ID_SUFFIX.match(col.name)
            if not m:
                continue
            candidate = m.group(1)
            # try plural/singular variants
            targets = [candidate, f"{candidate}s", f"{candidate}_spr"]
            for target in targets:
                if target in table_names and target != tname:
                    key = (tname, col.name, target, "id")
                    if key not in seen:
                        edges.append(key)
                        seen.add(key)
                    break
    return edges
