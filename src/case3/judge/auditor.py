"""Hybrid auditor: static + optional LLM."""

from __future__ import annotations

from typing import Any

from case3.config import Settings, get_settings
from case3.contracts import SecurityAuditor, is_approved
from case3.judge.llm import LLMJudge
from case3.judge.policy import analyze_task_policy
from case3.judge.static import StaticAnalyzer
from case3.llm.client import LLMClient, get_llm_client
from case3.models import AuditResult, Vulnerability
from case3.schema_index.parser import SchemaIndex


class HybridAuditor(SecurityAuditor):
    def __init__(
        self,
        llm: LLMClient | None = None,
        settings: Settings | None = None,
        schema_index: SchemaIndex | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or get_settings()
        self._llm = llm or get_llm_client(self._settings)
        self._schema_index = schema_index
        self._static = StaticAnalyzer(schema_index=schema_index)

    def audit(
        self,
        sql_query: str,
        task_description: str | None = None,
    ) -> AuditResult:
        findings = self._static.analyze(sql_query)
        llm_findings: list[Vulnerability] = []
        if task_description:
            findings = _merge_findings(findings, analyze_task_policy(task_description, sql_query))
            llm_findings = LLMJudge(self._llm, schema_index=self._schema_index).analyze_safe(
                sql_query, task_description=task_description
            )
        findings = _merge_findings(findings, llm_findings)

        overall = max((f.risk_score for f in findings), default=0.0)
        approved = is_approved(
            overall,
            findings,
            risk_threshold=self._settings.risk_threshold,
            hard_block_risk=self._settings.hard_block_risk,
        )
        summary = _build_summary(approved, overall, findings)
        return AuditResult(
            approved=approved,
            vulnerabilities=findings,
            overall_risk_score=overall,
            summary=summary,
        )


def _merge_findings(static: list[Vulnerability], llm: list[Vulnerability]) -> list[Vulnerability]:
    seen: set[tuple[str, int | None]] = set()
    out: list[Vulnerability] = []
    for v in static + llm:
        key = (v.vuln_class, v.line_hint)
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _build_summary(approved: bool, overall: float, findings: list[Vulnerability]) -> str:
    if approved:
        return f"Запрос одобрен. Итоговый риск: {overall:.1f}/10."
    classes = ", ".join(f.vuln_class for f in findings[:5])
    return f"Запрос отклонён. Риск: {overall:.1f}/10. Найдено: {classes}."
