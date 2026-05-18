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
from case3.judge.task_intent import (
    classify_task_intent_safe,
    non_actionable_task_finding,
    refusal_sql_for_non_actionable,
)
from case3.llm.client import LLMClient
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
        llm: LLMClient | None = None,
        risk_threshold: float = 4.0,
        hard_block_risk: float = 8.0,
    ) -> None:
        super().__init__(generator, auditor, max_iterations)
        self._timeout_sec = timeout_sec
        self._llm = llm
        self._risk_threshold = risk_threshold
        self._hard_block_risk = hard_block_risk

    def run(self, task_description: str) -> SystemResult:
        if task_requests_destruction(task_description):
            logger.warning("Task rejected (destructive intent): %s", task_description[:120])
            return self._refuse_destructive_task(task_description)

        if self._llm is not None:
            intent = classify_task_intent_safe(task_description, self._llm)
            if not intent.actionable:
                logger.warning(
                    "Task rejected (not actionable): %s — %s",
                    task_description[:80],
                    intent.reason,
                )
                return self._refuse_non_actionable_task(task_description, intent.reason)

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
            audit = self.auditor.audit(sql, task_description=task_description)
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
            if memory.is_stuck():
                logger.warning("Stopping: same vuln classes for 2 consecutive iterations")
                break

        stuck = memory.is_stuck() and not approved
        meta: dict[str, Any] = {
            "timeout_reached": time.monotonic() > deadline,
            "regression_detected": memory.detect_regression(last_audit) if last_audit else False,
            "stuck": stuck,
        }
        return finalize_result(
            task_description,
            iterations_log,
            final_sql,
            approved,
            metadata=meta,
            risk_threshold=self._risk_threshold,
            hard_block_risk=self._hard_block_risk,
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
            risk_threshold=self._risk_threshold,
            hard_block_risk=self._hard_block_risk,
        )

    def _refuse_non_actionable_task(self, task_description: str, reason: str) -> SystemResult:
        finding = non_actionable_task_finding(reason)
        refusal_sql = refusal_sql_for_non_actionable(reason)
        audit = AuditResult(
            approved=False,
            vulnerabilities=[finding],
            overall_risk_score=finding.risk_score,
            summary="Запрос отклонён: задача не является запросом к данным.",
        )
        log = IterationLog(
            timestamp=datetime.now(UTC),
            iteration=1,
            sql_query=refusal_sql,
            audit_result=audit,
            revision_notes="Отклонено до генерации SQL (проверка формулировки задачи).",
        )
        assert not is_approved(audit.overall_risk_score, audit.vulnerabilities)
        return finalize_result(
            task_description,
            [log],
            refusal_sql,
            approved=False,
            metadata={"refusal": "non_actionable_task", "refusal_reason": reason},
            risk_threshold=self._risk_threshold,
            hard_block_risk=self._hard_block_risk,
        )
