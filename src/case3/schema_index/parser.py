from __future__ import annotations

from collections.abc import Mapping

import sqlglot
from sqlglot import exp

from case3.models import ColumnInfo, ForeignKeyInfo, TableInfo


def parse_ddl(sql_text: str, *, sensitivity: Mapping[str, bool] | None = None) -> list[TableInfo]:
    """
    Minimal DDL parser for PostgreSQL CREATE TABLE statements.

    KISS constraints for MVP:
    - only extracts table name, column names + types
    - extracts FK constraints of the form: FOREIGN KEY (col) REFERENCES other(col)
    """
    sensitivity = sensitivity or {}

    tables: list[TableInfo] = []
    statements = sqlglot.parse(sql_text, read="postgres")

    for stmt in statements:
        if not isinstance(stmt, exp.Create):
            continue
        if stmt.args.get("kind") != "TABLE":
            continue

        table_expr = stmt.this
        if not isinstance(table_expr, exp.Schema):
            continue

        table_name = table_expr.this.name

        columns: list[ColumnInfo] = []
        fks: list[ForeignKeyInfo] = []

        for element in table_expr.expressions:
            if isinstance(element, exp.ColumnDef):
                col_name = element.this.name
                kind = element.args.get("kind")
                col_type = (
                    kind.sql(dialect="postgres") if isinstance(kind, exp.DataType) else "UNKNOWN"
                )
                columns.append(
                    ColumnInfo(
                        name=col_name,
                        data_type=col_type,
                        is_sensitive=bool(sensitivity.get(col_name.lower(), False)),
                    )
                )
                continue

            # Table-level constraint
            if isinstance(element, exp.Constraint):
                # In sqlglot, the FK is nested inside Constraint.expressions.
                fk_exprs = [e for e in element.expressions if isinstance(e, exp.ForeignKey)]
                if not fk_exprs:
                    continue

                # MVP: first FK only; only 1-column references supported.
                fk = fk_exprs[0]
                fk_cols = [c.name for c in fk.expressions if isinstance(c, exp.Identifier)]
                ref = fk.args.get("reference")
                if (
                    len(fk_cols) == 1
                    and isinstance(ref, exp.Reference)
                    and isinstance(ref.this, exp.Schema)
                    and isinstance(ref.this.this, exp.Table)
                    and len(ref.this.expressions) == 1
                    and isinstance(ref.this.expressions[0], exp.Identifier)
                ):
                    fks.append(
                        ForeignKeyInfo(
                            column=fk_cols[0],
                            ref_table=ref.this.this.name,
                            ref_column=ref.this.expressions[0].name,
                        )
                    )

        tables.append(TableInfo(name=table_name, columns=columns, foreign_keys=fks))

    return tables
