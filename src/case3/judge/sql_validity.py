"""Validate that generator output is an executable read-only SELECT."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from case3.models import Vulnerability

_NOT_SELECT_RISK = 9.0


def _strip_sql_comments(sql: str) -> str:
    without_line = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"/\*[\s\S]*?\*/", "", without_line).strip()


def is_read_only_select(sql: str) -> bool:
    """True when SQL parses to a query that includes a SELECT and no destructive DML."""
    body = _strip_sql_comments(sql)
    if not body:
        return False
    try:
        parsed = sqlglot.parse_one(body, dialect="postgres")
    except sqlglot.errors.ParseError:
        return False
    if parsed.find(exp.Delete) or parsed.find(exp.Drop):
        return False
    if re.search(r"\b(TRUNCATE|INSERT|UPDATE)\b", body, re.I):
        return False
    return parsed.find(exp.Select) is not None


def invalid_sql_finding(sql: str) -> Vulnerability:
    preview = sql.strip().replace("\n", " ")[:120]
    return Vulnerability(
        vuln_class="NOT_VALID_SELECT",
        risk_score=_NOT_SELECT_RISK,
        description=(f"Ответ не является исполняемым read-only SELECT (получено: {preview!r})."),
        recommendation="Сгенерируйте SELECT с явными колонками и LIMIT.",
    )


_KNOWN_NON_SELECT = re.compile(
    r"^\s*(DELETE|UPDATE|INSERT|TRUNCATE|DROP|GRANT|REVOKE|ALTER|CREATE|EXECUTE|DO|CALL)\b",
    re.I,
)


def analyze_sql_validity(sql: str) -> list[Vulnerability]:
    if is_read_only_select(sql):
        return []
    # Known dangerous statement types are caught by dedicated detectors
    # (DML_NO_WHERE, PRIV_ESCALATE, PLPGSQL_UNSAFE). NOT_VALID_SELECT is only
    # meaningful when the generator returns gibberish instead of a SELECT.
    body = _strip_sql_comments(sql)
    if _KNOWN_NON_SELECT.match(body):
        return []
    return [invalid_sql_finding(sql)]
