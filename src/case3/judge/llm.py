"""Optional LLM-based semantic audit."""

from __future__ import annotations

import json
import re

from case3.llm.client import LLMClient
from case3.models import Vulnerability
from case3.schema_index.parser import SchemaIndex

_AUDIT_PROMPT = """You are a PostgreSQL security auditor. Analyze the SQL and return JSON array only.
Each item: {{"vuln_class": "<KEY>", "risk_score": 0-10, "description": "...", "recommendation": "..."}}
Valid vuln_class keys: SQL_INJ_CLASSIC, SQL_INJ_UNION, DML_NO_WHERE, SELECT_STAR, DIRECT_SENSITIVE,
NO_PAGINATION, SQL_INJ_TIME, PRIV_ESCALATE, PLPGSQL_UNSAFE, TASK_SQL_MISMATCH.
If no issues, return [].

SQL:
{sql}

Schema context (truncated):
{schema}
{task_section}
"""

_TASK_SECTION = """
Natural language task:
{task}

Ignore greetings and polite filler; judge whether the SQL answers the data request in the task.
If there is no data request, or the SQL does not answer that data request,
emit exactly one finding: vuln_class TASK_SQL_MISMATCH, risk_score 9, with a clear description.
Do not flag mismatch only because the task started with a greeting.
"""


class LLMJudge:
    def __init__(self, llm: LLMClient, schema_index: SchemaIndex | None = None) -> None:
        self._llm = llm
        self._schema_snip = str(schema_index.model_dump() if schema_index else {})[:4000]

    def analyze(
        self,
        sql_query: str,
        task_description: str | None = None,
    ) -> list[Vulnerability]:
        task_section = ""
        if task_description and task_description.strip():
            task_section = _TASK_SECTION.format(task=task_description.strip())
        prompt = _AUDIT_PROMPT.format(
            sql=sql_query,
            schema=self._schema_snip,
            task_section=task_section,
        )
        raw = self._llm.complete(prompt)
        return _parse_findings(raw)

    def analyze_safe(
        self,
        sql_query: str,
        task_description: str | None = None,
    ) -> list[Vulnerability]:
        try:
            return self.analyze(sql_query, task_description=task_description)
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
