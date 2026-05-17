"""Baseline contracts (doc/baseline1.py)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from case3.models import AuditResult, SystemResult


class SQLGenerator(ABC):
    """Генерирует SQL по текстовому описанию задачи."""

    def __init__(self, db_schema: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self.db_schema = db_schema or {}
        self.kwargs = kwargs

    @abstractmethod
    def generate(
        self,
        task_description: str,
        sql_history: list[str] | None = None,
        audit_feedback: AuditResult | None = None,
        iteration: int = 1,
    ) -> str:
        """Return SQL string for the task."""


class SecurityAuditor(ABC):
    """Проверяет SQL-запрос на типовые уязвимости."""

    VULN_CLASSES: ClassVar[dict[str, str]] = {
        "SQL_INJ_CLASSIC": "SQL Injection (классический)",
        "SQL_INJ_UNION": "Union-based Injection",
        "DML_NO_WHERE": "UPDATE/DELETE без WHERE",
        "SELECT_STAR": "Избыточный SELECT *",
        "DIRECT_SENSITIVE": "Прямой доступ к чувствительным полям",
        "NO_PAGINATION": "Неограниченный LIMIT / отсутствие пагинации",
        "SQL_INJ_TIME": "Time-based blind Injection",
        "PRIV_ESCALATE": "Privilege Escalation через EXECUTE",
        "PLPGSQL_UNSAFE": "PL/pgSQL: небезопасный EXECUTE",
        "DESTRUCTIVE_DML": "DELETE / TRUNCATE / DROP в SQL",
        "TASK_DESTRUCTIVE": "Деструктивная формулировка задачи",
        "TASK_NOT_ACTIONABLE": "Задача не является запросом к данным",
        "TASK_SQL_MISMATCH": "SQL не соответствует формулировке задачи",
        "NOT_VALID_SELECT": "Нет исполняемого read-only SELECT",
    }
    RISK_THRESHOLD = 4.0
    HARD_BLOCK_RISK = 8.0

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    @abstractmethod
    def audit(
        self,
        sql_query: str,
        db_schema: dict[str, Any] | None = None,
        task_description: str | None = None,
    ) -> AuditResult:
        """Return audit result with vulnerabilities and approval flag."""


class SQLSecuritySystem(ABC):
    """Оркестрирует цикл генерация -> аудит -> исправление."""

    DEFAULT_MAX_ITERATIONS = 5

    def __init__(
        self,
        generator: SQLGenerator,
        auditor: SecurityAuditor,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.generator = generator
        self.auditor = auditor
        self.max_iterations = max_iterations

    @abstractmethod
    def run(self, task_description: str) -> SystemResult:
        """Run the full pipeline."""


def is_approved(
    overall_risk: float,
    vulnerabilities: list[Any],
    *,
    risk_threshold: float | None = None,
    hard_block_risk: float | None = None,
) -> bool:
    """Shared approval policy: risk <= threshold and no hard-block findings."""
    threshold = risk_threshold if risk_threshold is not None else SecurityAuditor.RISK_THRESHOLD
    block = hard_block_risk if hard_block_risk is not None else SecurityAuditor.HARD_BLOCK_RISK
    if overall_risk > threshold:
        return False
    return not any(v.risk_score >= block for v in vulnerabilities)
