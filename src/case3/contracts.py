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


def is_approved(overall_risk: float, vulnerabilities: list[Any]) -> bool:
    """Shared approval policy: risk <= threshold and no hard-block findings."""
    if overall_risk > SecurityAuditor.RISK_THRESHOLD:
        return False
    return not any(v.risk_score >= SecurityAuditor.HARD_BLOCK_RISK for v in vulnerabilities)
