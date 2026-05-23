"""Prompt templates for initial and repair generations."""

from __future__ import annotations

import re

from case3.models import AuditResult, Vulnerability
from case3.schema_index.retriever import TableContext

_BOILERPLATE = re.compile(r",?\s*(?:Sys|Abstract)\w*\{[^}]*\}")

_HARD_BLOCK_RISK = 8.0

_DOMAIN_CONTEXT = """\
You are a PostgreSQL expert working with a Russian corporate-lending database (Promsvyazbank).
Table naming convention: sys_ (system entities — employees, companies/counterparties), \
scp_ (СКП lending decisions), acc_ (accounting/ОСВ), yaig_ (guarantees), \
ms_ (multi-select links — never query directly).
Every table has 14 shared base columns (id, name, name__ru, name__en, status, \
create_date, org_id, user_id, …). Always prefer `name` over `name__ru`/`name__en`.
Key semantic facts:
- "Организации/компании" → sys_company. Do NOT use sys_obj_type or tbs_type.
- The initiator's human-readable name lives in sys_company, NOT in application_obj.name.
  JOIN sys_company only when filtering or selecting BY the initiator's name string.
- Generic "заявки" → application_obj. Subsystem-specific: scp_application (СКП), \
ic_application (ИУ), mler_application (МЮЭР), corp_tech_application (КТ).
Column names and comments may be in Russian or English.\
"""

_CORE_RULES = """\
Rules:
- Use column names EXACTLY as shown in the schema. Never invent column names.
- Qualify all tables with the `public.` schema prefix.
- Explicit column list (no SELECT *). Always include `id` when selecting rows.
- Use LIMIT for row-listing queries; pure aggregate queries (COUNT/MIN/MAX/SUM/AVG \
without GROUP BY) don't need LIMIT. GROUP BY queries are row-listing — add LIMIT.
- Column choice: prefer canonical `name` over `name__ru`/`name__en` unless the task \
explicitly asks for a locale ("на русском", "in English").
- Table for generic "заявки": use `application_obj`. Only switch to a subsystem table \
when the task names СКП/SCP, ИУ/IC, МЮЭР/MLER, or КТ explicitly.
- "По признаку X" / "по признаку участия/наличия в X" → GROUP BY the raw column X \
with COUNT(*). Do NOT filter (WHERE X = 1) and do NOT JOIN to a lookup table.
- Aggregates ("минимальный/максимальный/средний X") → MIN/MAX/AVG/SUM. \
Never substitute ORDER BY + LIMIT 1 for MIN or MAX.
- "с <col>" as a selection criterion (not sorting, not grouping) → include <col> in SELECT and \
add WHERE <col> IS NOT NULL. The word after "с" IS the column name — do not replace it with `name`. \
Example: "Сотрудники с org_id" → SELECT id, name, org_id … WHERE org_id IS NOT NULL LIMIT … \
Exception: "с именем инициатора" / "с именем X" → JOIN the lookup table to get the name string.
- "отсортированные по X" / "по возрастанию/убыванию X" → ORDER BY X only. Do NOT add WHERE X IS NOT NULL.
- "подсчёт/количество по X" / "по признаку X" → GROUP BY X with COUNT(*). Do NOT add WHERE X IS NOT NULL.
- JOIN sys_company for initiator name ONLY when the task says "по инициатору с именем, содержащим …" \
(filtering by the name string). For plain initiator_id lists, use the raw FK column without JOIN.
- Add WHERE only for conditions explicitly stated in the task. \
Do not invent IS NOT NULL, status = 1, or any filter not in the task.
- "без фильтра по X" / "без X" → no WHERE clause on X at all.
- When selecting a locale-specific column (name__ru, name__en, etc.), \
always add WHERE <that column> IS NOT NULL.\
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
{_CORE_RULES}
- Output exactly one SELECT query (read-only). Never use DELETE, TRUNCATE, DROP, INSERT, or UPDATE.
- If the message has no concrete data retrieval request (only greeting/chit-chat/meta), return only:
  -- Отказ: уточните задачу на естественном языке (что выбрать из БД).
- If the message has a greeting plus a data request, ignore the greeting and generate SQL for the data part.
- Use the LIMIT value from the task ("лимит N", "не более N", "N записей"); otherwise default 10–100.
- Never use placeholder literals ('your_X_here', '<replace_me>', '???'). If a specific value is missing, use IS NOT NULL or a broad filter.
- For sensitive/PII columns (marked [PII] in schema): replace with '***' AS column_name.
- WHERE conditions: "активные" → status = 1; "у которых заполнен X" / "с X" → X IS NOT NULL; "после даты Y" → date comparison; "содержит строку" → ILIKE.
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

    return f"""{_DOMAIN_CONTEXT}
REPAIR: Fix the PostgreSQL query based on security audit feedback.
{_CORE_RULES}

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
