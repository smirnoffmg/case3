"""Human-readable audit report."""

from __future__ import annotations

from typing import Any

from case3.models import IterationLog, SystemResult


def build_audit_log(
    task: str,
    iterations_log: list[IterationLog],
    final_sql: str,
    approved: bool,
) -> str:
    lines = [
        "# Отчёт аудита SQL",
        "",
        f"**Задача:** {task}",
        f"**Итог:** {'Одобрено' if approved else 'Не одобрено'}",
        f"**Итераций:** {len(iterations_log)}",
        "",
        "## Итоговый SQL",
        "```sql",
        final_sql,
        "```",
        "",
        "## Ход итераций",
    ]
    for entry in iterations_log:
        lines.append(f"### Итерация {entry.iteration}")
        lines.append(f"- Время: {entry.timestamp.isoformat()}")
        lines.append(f"- Риск: {entry.audit_result.overall_risk_score:.1f}/10")
        lines.append(f"- Одобрено: {entry.audit_result.approved}")
        if entry.revision_notes:
            lines.append(f"- Заметки: {entry.revision_notes}")
        lines.append("")
        lines.append("```sql")
        lines.append(entry.sql_query)
        lines.append("```")
        if entry.audit_result.vulnerabilities:
            lines.append("")
            lines.append("**Замечания:**")
            for v in entry.audit_result.vulnerabilities:
                lines.append(f"- `{v.vuln_class}` (risk {v.risk_score}): {v.description}")
        lines.append("")
    if approved:
        lines.append("## Обоснование одобрения")
        lines.append(
            "Запрос прошёл проверку: итоговый риск в пределах порога "
            "и нет критических уязвимостей (risk >= 8)."
        )
    else:
        lines.append("## Причина отклонения")
        refusal_classes = (
            "TASK_DESTRUCTIVE",
            "DESTRUCTIVE_DML",
            "TASK_NOT_ACTIONABLE",
            "TASK_SQL_MISMATCH",
        )
        refusal_findings = [
            v
            for v in (iterations_log[-1].audit_result.vulnerabilities if iterations_log else [])
            if v.vuln_class in refusal_classes
        ]
        if refusal_findings:
            lines.append(refusal_findings[0].description)
        elif iterations_log:
            lines.append(iterations_log[-1].audit_result.summary)
    return "\n".join(lines)


def finalize_result(
    task: str,
    iterations_log: list[IterationLog],
    final_sql: str,
    approved: bool,
    metadata: dict[str, Any] | None = None,
) -> SystemResult:
    return SystemResult(
        final_sql=final_sql,
        approved=approved,
        iterations_used=len(iterations_log),
        iterations_log=iterations_log,
        audit_log=build_audit_log(task, iterations_log, final_sql, approved),
        metadata=metadata or {},
    )
