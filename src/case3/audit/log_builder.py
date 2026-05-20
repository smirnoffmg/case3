"""Human-readable audit report."""

from __future__ import annotations

from typing import Any

from case3.models import AuditResult, IterationLog, SystemResult


def _iteration_decision_line(
    audit: AuditResult,
    risk_threshold: float,
    hard_block_risk: float,
) -> str:
    """One-line explanation of why this iteration was approved or rejected."""
    hard = [v for v in audit.vulnerabilities if v.risk_score >= hard_block_risk]
    risk = audit.overall_risk_score
    if hard:
        cls = ", ".join(f"`{v.vuln_class}`" for v in hard)
        return (
            f"- **Решение:** отклонено — hard-block {cls} "
            f"(risk {hard[0].risk_score:.1f} ≥ {hard_block_risk:.1f})."
        )
    if audit.approved:
        return (
            f"- **Решение:** одобрено — риск {risk:.1f} ≤ порога {risk_threshold:.1f} "
            f"и нет hard-block (≥ {hard_block_risk:.1f})."
        )
    return f"- **Решение:** отклонено — риск {risk:.1f} > порога {risk_threshold:.1f}."


def build_audit_log(
    task: str,
    iterations_log: list[IterationLog],
    final_sql: str,
    approved: bool,
    risk_threshold: float = 4.0,
    hard_block_risk: float = 8.0,
) -> str:
    lines = [
        "# Отчёт аудита SQL",
        "",
        f"**Задача:** {task}",
        f"**Итог:** {'Одобрено' if approved else 'Не одобрено'}",
        f"**Итераций:** {len(iterations_log)}",
        "",
        "## Параметры аудита",
        f"- Порог одобрения: риск ≤ **{risk_threshold:.1f}** (max по находкам)",
        f"- Hard-block: любая находка с риском ≥ **{hard_block_risk:.1f}**",
        f"- Правило: одобрено ⇔ `max_risk ≤ {risk_threshold:.1f}` "
        f"**И** нет находок с риском ≥ `{hard_block_risk:.1f}`",
        "",
        "## Итоговый SQL",
        "```sql",
        final_sql,
        "```",
        "",
        "## Ход итераций",
    ]
    for entry in iterations_log:
        audit = entry.audit_result
        lines.append(f"### Итерация {entry.iteration}")
        lines.append(f"- Время: {entry.timestamp.isoformat()}")
        lines.append(f"- Риск: {audit.overall_risk_score:.1f}/10")
        lines.append(f"- Одобрено: {audit.approved}")
        lines.append(_iteration_decision_line(audit, risk_threshold, hard_block_risk))
        if entry.revision_notes:
            lines.append(f"- Заметки: {entry.revision_notes}")
        lines.append("")
        lines.append("```sql")
        lines.append(entry.sql_query)
        lines.append("```")
        if audit.vulnerabilities:
            lines.append("")
            lines.append("**Замечания:**")
            for v in audit.vulnerabilities:
                marker = " ⛔ HARD-BLOCK" if v.risk_score >= hard_block_risk else ""
                lines.append(f"- `{v.vuln_class}` (risk {v.risk_score}){marker}: {v.description}")
        lines.append("")
    if approved:
        last_risk = iterations_log[-1].audit_result.overall_risk_score if iterations_log else 0.0
        lines.append("## Обоснование одобрения")
        lines.append(
            f"`final_risk = {last_risk:.1f} ≤ {risk_threshold:.1f}` "
            f"AND `no hard-block (≥ {hard_block_risk:.1f})` → **APPROVED**."
        )
    else:
        lines.append("## Причина отклонения")
        last_vulns = iterations_log[-1].audit_result.vulnerabilities if iterations_log else []
        last_risk = iterations_log[-1].audit_result.overall_risk_score if iterations_log else 0.0
        refusal_classes = (
            "TASK_DESTRUCTIVE",
            "DESTRUCTIVE_DML",
            "TASK_NOT_ACTIONABLE",
            "TASK_SQL_MISMATCH",
        )
        hard_blocks = [v for v in last_vulns if v.risk_score >= hard_block_risk]
        refusal_findings = [v for v in last_vulns if v.vuln_class in refusal_classes]
        if refusal_findings:
            lines.append(refusal_findings[0].description)
        elif hard_blocks:
            classes = ", ".join(f"`{v.vuln_class}`" for v in hard_blocks)
            lines.append(
                f"Блокирующая уязвимость: {classes} "
                f"(risk {hard_blocks[0].risk_score:.1f} ≥ {hard_block_risk:.1f})."
            )
        elif iterations_log:
            lines.append(
                f"Итоговый риск {last_risk:.1f} превышает порог {risk_threshold:.1f}. "
                + iterations_log[-1].audit_result.summary
            )
    return "\n".join(lines)


def finalize_result(
    task: str,
    iterations_log: list[IterationLog],
    final_sql: str,
    approved: bool,
    metadata: dict[str, Any] | None = None,
    risk_threshold: float = 4.0,
    hard_block_risk: float = 8.0,
) -> SystemResult:
    return SystemResult(
        final_sql=final_sql,
        approved=approved,
        iterations_used=len(iterations_log),
        iterations_log=iterations_log,
        audit_log=build_audit_log(
            task, iterations_log, final_sql, approved, risk_threshold, hard_block_risk
        ),
        metadata=metadata or {},
    )
