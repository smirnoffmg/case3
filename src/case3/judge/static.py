from __future__ import annotations

from collections.abc import Iterable

import sqlglot
from sqlglot import exp

from case3.models import Finding, SqlCandidate, TableInfo, VulnerabilityClass


def _sensitive_column_names(schema: Iterable[TableInfo]) -> set[str]:
    names: set[str] = set()
    for t in schema:
        for c in t.columns:
            if c.is_sensitive:
                names.add(c.name.lower())
    return names


def _find_star_select(stmt: exp.Expression) -> bool:
    return any(isinstance(node, exp.Star) for node in stmt.walk())


def _find_column_projection_names(stmt: exp.Expression) -> set[str]:
    """
    Best-effort: collect explicit projection column names.
    """
    names: set[str] = set()
    select = stmt.find(exp.Select)
    if select is None:
        return names
    for proj in select.expressions:
        if isinstance(proj, exp.Column):
            names.add(proj.name.lower())
            continue
        col = proj.find(exp.Column)
        if col is not None:
            names.add(col.name.lower())
    return names


class StaticJudge:
    def review(self, candidate: SqlCandidate, *, schema: list[TableInfo]) -> list[Finding]:
        sql = candidate.sql.strip()
        sql_lower = sql.lower()
        findings: list[Finding] = []

        try:
            stmt: exp.Expression = sqlglot.parse_one(sql, read="postgres")  # type: ignore[assignment]
        except Exception:
            # If we can't parse, treat as high-risk for safety.
            return [
                Finding(
                    vulnerability_class=VulnerabilityClass.sql_injection,
                    risk=10,
                    explanation="SQL could not be parsed; reject as unsafe.",
                    location=None,
                    suggested_fix="Rewrite query as valid PostgreSQL and avoid string concatenation.",
                    source="static",
                )
            ]

        # UPDATE/DELETE without WHERE
        if isinstance(stmt, (exp.Delete, exp.Update)) and stmt.args.get("where") is None:
            findings.append(
                Finding(
                    vulnerability_class=VulnerabilityClass.update_delete_without_where,
                    risk=9,
                    explanation="UPDATE/DELETE without WHERE can affect all rows.",
                    location=None,
                    suggested_fix="Add a WHERE clause that scopes the affected rows.",
                    source="static",
                )
            )

        # UNION usage
        if " union " in f" {sql_lower} ":
            findings.append(
                Finding(
                    vulnerability_class=VulnerabilityClass.union_based_injection,
                    risk=9,
                    explanation="UNION in user-facing queries is commonly used in injection patterns.",
                    location=None,
                    suggested_fix="Avoid UNION unless strictly necessary; parameterize inputs.",
                    source="static",
                )
            )

        # Time-based blind injection (pg_sleep)
        if "pg_sleep" in sql_lower:
            findings.append(
                Finding(
                    vulnerability_class=VulnerabilityClass.time_based_blind_injection,
                    risk=8,
                    explanation="pg_sleep is a common time-based injection primitive.",
                    location=None,
                    suggested_fix="Remove pg_sleep; do not expose timing primitives.",
                    source="static",
                )
            )

        # SELECT * (overfetching)
        if isinstance(stmt, exp.Select) and _find_star_select(stmt):
            findings.append(
                Finding(
                    vulnerability_class=VulnerabilityClass.select_star,
                    risk=5,
                    explanation="SELECT * may overfetch data and increase exposure.",
                    location=None,
                    suggested_fix="Select only required columns explicitly.",
                    source="static",
                )
            )

        # Sensitive fields access
        select_node = stmt.find(exp.Select)
        if select_node is not None:
            sensitive = _sensitive_column_names(schema)
            projected = _find_column_projection_names(stmt)
            if sensitive.intersection(projected):
                findings.append(
                    Finding(
                        vulnerability_class=VulnerabilityClass.direct_access_sensitive_fields,
                        risk=6,
                        explanation="Query selects sensitive fields from schema tags.",
                        location=None,
                        suggested_fix="Avoid selecting sensitive fields unless absolutely required.",
                        source="static",
                    )
                )

        # Missing LIMIT for read queries
        selects = list(stmt.find_all(exp.Select))
        if selects and any(s.args.get("limit") is None for s in selects):
            findings.append(
                Finding(
                    vulnerability_class=VulnerabilityClass.missing_limit,
                    risk=4,
                    explanation="SELECT without LIMIT can scan large datasets.",
                    location=None,
                    suggested_fix="Add LIMIT (or pagination) appropriate for the use-case.",
                    source="static",
                )
            )

        return findings
