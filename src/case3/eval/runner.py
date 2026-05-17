"""Batch evaluation runner."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from case3.config import Settings, get_settings
from case3.eval.metrics import (
    JudgeMetrics,
    PipelineMetrics,
    compare_vuln_classes,
    load_jsonl,
    sql_match,
)
from case3.judge.auditor import HybridAuditor
from case3.judge.static import StaticAnalyzer
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import load_schema_index, to_baseline_dict

logger = logging.getLogger(__name__)


def run_eval(settings: Settings | None = None, limit: int | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    index = load_schema_index(settings.schema_json_path)
    db_schema = to_baseline_dict(index)

    tasks = load_jsonl(settings.dataset_tasks_path)
    vulns = load_jsonl(settings.dataset_vulns_path)
    if limit:
        tasks = tasks[:limit]
        vulns = vulns[:limit]

    pipeline_m = PipelineMetrics()
    judge_m = JudgeMetrics()
    static = StaticAnalyzer()
    auditor = HybridAuditor()

    results: list[dict[str, Any]] = []

    logger.info("Eval: %s pipeline tasks, %s vuln samples", len(tasks), len(vulns))
    for i, row in enumerate(tasks, start=1):
        task = row["task"]
        gold = row.get("sql", "")
        logger.info("[%s/%s] %s", i, len(tasks), task[:80])
        result = run_sql_security_pipeline(task, db_schema=db_schema)
        logger.info(
            "  -> approved=%s iterations=%s",
            result.approved,
            result.iterations_used,
        )
        pipeline_m.total += 1
        if result.approved:
            pipeline_m.approved += 1
        pipeline_m.total_iterations += result.iterations_used
        if gold and sql_match(result.final_sql, gold):
            pipeline_m.execution_matches += 1
        risks = [e.audit_result.overall_risk_score for e in result.iterations_log]
        if len(risks) >= 2:
            pipeline_m.risk_deltas.append(risks[0] - risks[-1])
        results.append(
            {
                "task": task,
                "approved": result.approved,
                "iterations": result.iterations_used,
                "final_sql": result.final_sql,
            }
        )

    for row in vulns:
        sql = row["sql"]
        expected = set(row.get("expected_classes", []))
        findings = static.analyze(sql, db_schema)
        predicted = {f.vuln_class for f in findings}
        compare_vuln_classes(predicted, expected, judge_m)
        # also test hybrid without llm
        audit = auditor.audit(sql, db_schema)
        compare_vuln_classes({f.vuln_class for f in audit.vulnerabilities}, expected, judge_m)

    _, llm_base = settings.resolve_llm_credentials()
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "llm": {
            "model": settings.openai_model,
            "base_url": llm_base,
            "use_llm_judge": settings.use_llm,
        },
        "pipeline": {
            "total": pipeline_m.total,
            "approval_rate": pipeline_m.approval_rate,
            "mean_iterations": pipeline_m.mean_iterations,
            "execution_accuracy": pipeline_m.execution_accuracy,
            "mean_risk_delta": (
                sum(pipeline_m.risk_deltas) / len(pipeline_m.risk_deltas)
                if pipeline_m.risk_deltas
                else 0.0
            ),
        },
        "judge": {
            "precision": judge_m.precision,
            "recall": judge_m.recall,
        },
        "samples": results[:10],
    }

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out = settings.reports_dir / f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(out)
    return report
