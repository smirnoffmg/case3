"""Orchestrator: generate -> audit -> repair loop."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from case3.audit.log_builder import finalize_result
from case3.contracts import SecurityAuditor, SQLGenerator, SQLSecuritySystem
from case3.generator.prompt_rag import PromptRAGGenerator
from case3.memory.feedback import FeedbackMemory
from case3.models import IterationLog, SystemResult


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
        deadline = time.monotonic() + self._timeout_sec
        memory = FeedbackMemory()
        sql_history: list[str] = []
        iterations_log: list[IterationLog] = []
        last_audit = None
        final_sql = ""
        approved = False

        for iteration in range(1, self.max_iterations + 1):
            if time.monotonic() > deadline:
                break

            if isinstance(self.generator, PromptRAGGenerator):
                self.generator.set_lessons(memory.lessons())

            sql = self.generator.generate(
                task_description,
                sql_history=sql_history or None,
                audit_feedback=last_audit,
                iteration=iteration,
            )
            sql_history.append(sql)
            audit = self.auditor.audit(sql, self.generator.db_schema)
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
            if approved:
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
