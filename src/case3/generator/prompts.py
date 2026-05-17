"""Prompt templates for initial and repair generations."""

from __future__ import annotations

from case3.models import AuditResult, Vulnerability
from case3.schema_index.retriever import TableContext


def format_schema_context(tables: list[TableContext]) -> str:
    lines = []
    for t in tables:
        lines.append(f"Table: {t.name}")
        if t.comment:
            lines.append(f"  Comment: {t.comment}")
        lines.append(f"  Columns: {t.columns_text}")
    return "\n".join(lines)


def format_vulnerabilities(vulns: list[Vulnerability]) -> str:
    if not vulns:
        return "Нет замечаний."
    return "\n".join(
        f"- [{v.vuln_class}] risk={v.risk_score}: {v.description} | Fix: {v.recommendation}"
        for v in vulns
    )


def build_initial_prompt(
    task: str,
    schema_context: str,
    few_shot: str = "",
) -> str:
    return f"""You are a PostgreSQL expert. Generate a single safe read-only PostgreSQL SELECT for the task.
Rules:
- Output exactly one SELECT query (read-only). Never use DELETE, TRUNCATE, DROP, INSERT, or UPDATE.
- Listing or reporting data (including "all" rows) is allowed: use SELECT with an appropriate LIMIT.
- Explicit column list (no SELECT *), always include LIMIT, avoid sensitive columns unless required.
Dialect: PostgreSQL.

Schema:
{schema_context}

{few_shot}

Task: {task}

Return only SQL in a ```sql fenced block.
"""


def build_repair_prompt(
    task: str,
    sql_history: list[str],
    audit_feedback: AuditResult | None,
    lessons: list[str],
    schema_context: str,
) -> str:
    history = "\n---\n".join(sql_history[-3:]) if sql_history else ""
    vulns = format_vulnerabilities(audit_feedback.vulnerabilities if audit_feedback else [])
    lesson_text = "\n".join(f"- {lesson}" for lesson in lessons) or "Нет."
    return f"""REPAIR: Fix the PostgreSQL query based on security audit feedback.

Schema:
{schema_context}

Task: {task}

Previous SQL attempts:
{history}

Audit findings:
{vulns}

Accumulated lessons (do not repeat these mistakes):
{lesson_text}

Generate an improved safe SQL query. Return only SQL in ```sql block.
"""
