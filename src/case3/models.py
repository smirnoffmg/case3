"""Baseline dataclasses (doc/baseline1.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Vulnerability:
    """Найденная уязвимость."""

    vuln_class: str
    risk_score: float
    description: str
    recommendation: str
    line_hint: int | None = None


@dataclass
class AuditResult:
    """Результат проверки SQL."""

    approved: bool
    vulnerabilities: list[Vulnerability]
    overall_risk_score: float
    summary: str


@dataclass
class IterationLog:
    """Лог одной итерации."""

    timestamp: datetime
    iteration: int
    sql_query: str
    audit_result: AuditResult
    revision_notes: str = ""


@dataclass
class SystemResult:
    """Финальный результат системы."""

    final_sql: str
    approved: bool
    iterations_used: int
    iterations_log: list[IterationLog]
    audit_log: str
    metadata: dict[str, Any] = field(default_factory=dict)
