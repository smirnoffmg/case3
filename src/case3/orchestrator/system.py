"""Orchestrator: generate -> audit -> repair loop."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from case3.audit.log_builder import finalize_result
from case3.contracts import SecurityAuditor, SQLGenerator, SQLSecuritySystem, is_approved
from case3.generator.prompt_rag import PromptRAGGenerator
from case3.judge.policy import destructive_task_finding, task_requests_destruction
from case3.memory.feedback import FeedbackMemory
from case3.models import AuditResult, IterationLog, SystemResult

logger = logging.getLogger(__name__)

_REFUSAL_SQL = (
    "-- Отказ: запросы на удаление или уничтожение данных (DELETE, TRUNCATE, DROP) "
    "не поддерживаются. Переформулируйте задачу как безопасный SELECT."
)


class Orchestrator(SQLSecuritySystem):
    def __init__(
        self,
        generator: SQLGenerator,
        auditor: SecurityAuditor,
        max_iterations: int = SQLSecuritySystem.DEFAULT_MAX_ITERATIONS,
        timeout_sec: float = 60.0,
    ) -> None:
        super().__init__(generator, auditor, max_iterations)
        self._timeout_sec = timeout_sec

    def run(self, task_description: str) -> SystemResult:
        if task_requests_destruction(task_description):
            logger.warning("Task rejected (destructive intent): %s", task_description[:120])
            return self._refuse_destructive_task(task_description)

        logger.info("Task: %s", task_description)
        deadline = time.monotonic() + self._timeout_sec
        memory = FeedbackMemory()
        sql_history: list[str] = []
        iterations_log: list[IterationLog] = []
        last_audit = None
        final_sql = ""
        approved = False

        for iteration in range(1, self.max_iterations + 1):
            if time.monotonic() > deadline:
                logger.warning("Timeout reached before iteration %s", iteration)
                break

            logger.info("--- Iteration %s/%s ---", iteration, self.max_iterations)
            if isinstance(self.generator, PromptRAGGenerator):
                self.generator.set_lessons(memory.lessons())

            sql = self.generator.generate(
                task_description,
                sql_history=sql_history or None,
                audit_feedback=last_audit,
                iteration=iteration,
            )
            sql_history.append(sql)
            logger.debug("SQL:\n%s", sql)
            audit = self.auditor.audit(
                sql,
                self.generator.db_schema,
                task_description=task_description,
            )
            memory.update(audit, iteration)
            note = memory.revision_note(audit, iteration)

            iterations_log.append(
                IterationLog(
                    timestamp=datetime.now(UTC),
                    iteration=iteration,
                    sql_query=sql,
                    audit_result=audit,
                    revision_notes=note,
                )
            )
            final_sql = sql
            approved = audit.approved
            last_audit = audit
            logger.info(
                "Audit: risk=%.1f approved=%s | %s",
                audit.overall_risk_score,
                approved,
                audit.summary,
            )
            for v in audit.vulnerabilities:
                logger.info("  [%s] risk=%.1f %s", v.vuln_class, v.risk_score, v.description)
            if note:
                logger.debug("Revision notes: %s", note)
            if approved:
                logger.info("Stopping: query approved")
                break

        meta: dict[str, Any] = {
            "timeout_reached": time.monotonic() > deadline,
            "regression_detected": memory.detect_regression(last_audit) if last_audit else False,
        }
        return finalize_result(
            task_description,
            iterations_log,
            final_sql,
            approved,
            metadata=meta,
        )

    def _refuse_destructive_task(self, task_description: str) -> SystemResult:
        finding = destructive_task_finding()
        audit = AuditResult(
            approved=False,
            vulnerabilities=[finding],
            overall_risk_score=finding.risk_score,
            summary="Запрос отклонён: деструктивная формулировка задачи.",
        )
        log = IterationLog(
            timestamp=datetime.now(UTC),
            iteration=1,
            sql_query=_REFUSAL_SQL,
            audit_result=audit,
            revision_notes="Отклонено до генерации SQL.",
        )
        assert not is_approved(audit.overall_risk_score, audit.vulnerabilities)
        return finalize_result(
            task_description,
            [log],
            _REFUSAL_SQL,
            approved=False,
            metadata={"refusal": "destructive_task"},
        )
