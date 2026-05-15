"""Optional LLM-based semantic audit."""

from __future__ import annotations

import json
import re
from typing import Any

from case3.llm.client import LLMClient
from case3.models import Vulnerability

_AUDIT_PROMPT = """You are a PostgreSQL security auditor. Analyze the SQL and return JSON array only.
Each item: {{"vuln_class": "<KEY>", "risk_score": 0-10, "description": "...", "recommendation": "..."}}
Valid vuln_class keys: SQL_INJ_CLASSIC, SQL_INJ_UNION, DML_NO_WHERE, SELECT_STAR, DIRECT_SENSITIVE,
NO_PAGINATION, SQL_INJ_TIME, PRIV_ESCALATE, PLPGSQL_UNSAFE.
If no issues, return [].

SQL:
{sql}

Schema context (truncated):
{schema}
"""


class LLMJudge:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def analyze(
        self, sql_query: str, db_schema: dict[str, Any] | None = None
    ) -> list[Vulnerability]:
        schema_snip = str(db_schema or {})[:4000]
        prompt = _AUDIT_PROMPT.format(sql=sql_query, schema=schema_snip)
        raw = self._llm.complete(prompt)
        return _parse_findings(raw)

    def analyze_safe(
        self, sql_query: str, db_schema: dict[str, Any] | None = None
    ) -> list[Vulnerability]:
        try:
            return self.analyze(sql_query, db_schema)
        except (json.JSONDecodeError, KeyError, TypeError):
            return []


def _parse_findings(raw: str) -> list[Vulnerability]:
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []
    data = json.loads(m.group(0))
    out: list[Vulnerability] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(
            Vulnerability(
                vuln_class=str(item.get("vuln_class", "SQL_INJ_CLASSIC")),
                risk_score=float(item.get("risk_score", 5.0)),
                description=str(item.get("description", "")),
                recommendation=str(item.get("recommendation", "")),
            )
        )
    return out
