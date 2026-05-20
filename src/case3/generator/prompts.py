"""Prompt templates for initial and repair generations."""

from __future__ import annotations

import re

from case3.models import AuditResult, Vulnerability
from case3.schema_index.retriever import TableContext

_BOILERPLATE = re.compile(r",?\s*(?:Sys|Abstract)\w*\{[^}]*\}")

_HARD_BLOCK_RISK = 8.0

_DOMAIN_CONTEXT = """\
You are a PostgreSQL expert working with a Russian banking system database.
Table naming convention: sys_ (system objects/employees), scp_ (lending/SCP), \
acc_ (accounting), yaig_ (guarantees/agreements), ms_ (multi-select links).
Column names and comments may be in Russian or English.\
"""


def _clean_comment(s: str) -> str:
    return _BOILERPLATE.sub("", s).strip().strip(",").strip()


def format_schema_context(tables: list[TableContext]) -> str:
    lines = []
    for t in tables:
        lines.append(f"Table: {t.name}")
        comment = _clean_comment(t.comment)
        if comment:
            lines.append(f"  Comment: {comment}")
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
    return f"""{_DOMAIN_CONTEXT}
Generate a single safe read-only PostgreSQL SELECT for the task.
Rules:
- Output exactly one SELECT query (read-only). Never use DELETE, TRUNCATE, DROP, INSERT, or UPDATE.
- If the message has no concrete data retrieval request (only greeting/chit-chat/meta), return only:
  -- Отказ: уточните задачу на естественном языке (что выбрать из БД).
- If the message has a greeting plus a data request, ignore the greeting and generate SQL for the data part.
- Listing or reporting data (including "all" rows) is allowed: use SELECT with an appropriate LIMIT.
- Explicit column list (no SELECT *). Use LIMIT for row-listing queries; aggregate queries (COUNT/MIN/MAX/SUM/AVG without GROUP BY) don't need LIMIT.
- Add WHERE only when the task explicitly asks for it (e.g. "активные" → status = 1, "у которых заполнен X" / "с X" / "по X" → X IS NOT NULL, "после даты Y" → date comparison, "содержит/начинается с строки" → ILIKE). Do not invent filters that aren't in the task.
- Never use placeholder literals like 'your_X_here', '<replace_me>' or any '???'. If the task lacks a specific value, use IS NOT NULL or the appropriate broad filter.
- Use the LIMIT value mentioned in the task ("лимит N", "не более N", "N записей"); otherwise pick a reasonable default (10–100).
- Column choice: when both a canonical column (`name`, `description`) and locale-suffixed variants (`name__ru`, `name__en`, `description__ru`) exist on the same table, prefer the canonical column unless the task explicitly asks for a specific locale ("на русском", "in English").
- Table choice for "заявки/applications": the schema has parallel application streams — use `application_obj` for generic "заявки" without subsystem name. Only use `scp_application` if the task mentions СКП/SCP, `ic_application` for ИУ/IC, `mler_application` for МЮЭР/MLER, `corp_tech_application` for КТ/корпоративные техзаявки.
- For sensitive/PII columns (marked [PII] in schema): replace with a fixed mask literal '***' AS column_name — never use current_setting(), session_user, or role-based CASE logic.
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
    raw_vulns = audit_feedback.vulnerabilities if audit_feedback else []
    sorted_vulns = sorted(raw_vulns, key=lambda v: v.risk_score, reverse=True)
    vulns_text = format_vulnerabilities(sorted_vulns)
    lesson_text = "\n".join(f"- {lesson}" for lesson in lessons) or "Нет."

    top = sorted_vulns[0] if sorted_vulns else None
    critical_note = ""
    if top and top.risk_score >= _HARD_BLOCK_RISK:
        critical_note = (
            f"\nCRITICAL: fix [{top.vuln_class}] first (risk={top.risk_score:.0f}) — "
            "this is a hard block that will reject the query regardless of other issues."
        )

    return f"""REPAIR: Fix the PostgreSQL query based on security audit feedback.

Schema:
{schema_context}

Task: {task}

Previous SQL attempts:
{history}

Audit findings (sorted by risk, highest first):{critical_note}
{vulns_text}

Accumulated lessons (do not repeat these mistakes):
{lesson_text}

Generate an improved safe SQL query. Return only SQL in ```sql block.
"""
