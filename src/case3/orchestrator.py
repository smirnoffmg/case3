from __future__ import annotations

from case3.config import Config
from case3.generator.base import Generator
from case3.judge.base import Judge, combine_findings
from case3.memory import CritiqueMemory
from case3.models import CritiqueLesson, Finding, OrchestratorState, RunResult, TableInfo
from case3.schema_index.retriever import SchemaRetriever


def run(
    task: str,
    *,
    generator: Generator,
    judges: list[Judge],
    memory: CritiqueMemory,
    retriever: SchemaRetriever,
    full_schema: list[TableInfo],
    config: Config,
) -> RunResult:
    findings_per_iter: list[list[Finding]] = []
    lessons_per_iter: list[list[CritiqueLesson]] = []

    lessons = memory.lessons()
    final_sql: str | None = None

    for iteration in range(config.max_iters):
        schema_ctx = retriever.retrieve(task, k=min(5, len(full_schema)))
        candidate = generator.generate(
            task,
            schema=schema_ctx,
            lessons=lessons,
            iteration=iteration,
        )
        final_sql = candidate.sql

        findings_lists = [j.review(candidate, schema=full_schema) for j in judges]
        findings = combine_findings(findings_lists)
        findings_per_iter.append(findings)

        static_block = any(
            f.source == "static" and f.risk >= config.hard_block_risk_threshold for f in findings
        )
        max_risk = max((f.risk for f in findings), default=0)
        approved = (not findings) or (not static_block and max_risk < config.approve_risk_threshold)

        if approved:
            return RunResult(
                final_state=OrchestratorState.approved,
                iterations=iteration + 1,
                final_sql=final_sql,
                findings_per_iter=findings_per_iter,
                lessons_per_iter=lessons_per_iter,
            )

        new_lessons = memory.distill(findings)
        lessons_per_iter.append(new_lessons)
        lessons = memory.lessons()

    return RunResult(
        final_state=OrchestratorState.exhausted,
        iterations=config.max_iters,
        final_sql=final_sql,
        findings_per_iter=findings_per_iter,
        lessons_per_iter=lessons_per_iter,
    )
