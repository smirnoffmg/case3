"""Task-level safety policy (destructive intent, SQL/task mismatch)."""

from __future__ import annotations

import re

from case3.models import Vulnerability

# Natural-language signals that the user wants destructive DML.
# Do not use short prefixes like «сотр» — they match inside «сотрудник».
_DESTRUCTIVE_TASK_RE = re.compile(
    r"(?i)"
    r"\b(delete|truncate|drop|remove|wipe)\b|"
    r"(?:^|\s)(удал\w+|уничтож\w+|стерт\w+|выпил\w+|очист\w+)",
)

# Destructive statements in SQL (with or without WHERE).
_DESTRUCTIVE_SQL_RE = re.compile(
    r"(?i)\b(DELETE|TRUNCATE|DROP)\b",
)


def task_requests_destruction(task: str) -> bool:
    return bool(_DESTRUCTIVE_TASK_RE.search(task.strip()))


def sql_contains_destructive_dml(sql: str) -> bool:
    return bool(_DESTRUCTIVE_SQL_RE.search(sql))


def destructive_task_finding() -> Vulnerability:
    return Vulnerability(
        vuln_class="TASK_DESTRUCTIVE",
        risk_score=9.0,
        description=(
            "Задача требует деструктивной операции (удаление, TRUNCATE, DROP). "
            "Такие запросы не генерируются и не одобряются."
        ),
        recommendation="Переформулируйте задачу как безопасный read-only запрос (SELECT с LIMIT).",
    )


def destructive_sql_finding() -> Vulnerability:
    return Vulnerability(
        vuln_class="DESTRUCTIVE_DML",
        risk_score=10.0,
        description="В запросе есть DELETE, TRUNCATE или DROP.",
        recommendation="Используйте только безопасные read-only SELECT-запросы.",
    )


def analyze_task_policy(task: str, sql: str) -> list[Vulnerability]:
    """Reject when the NL task is destructive or SQL contains destructive DML."""
    findings: list[Vulnerability] = []
    if task_requests_destruction(task):
        findings.append(destructive_task_finding())
    if sql_contains_destructive_dml(sql):
        findings.append(destructive_sql_finding())
    return findings
