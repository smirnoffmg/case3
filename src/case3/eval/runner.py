"""Batch evaluation runner."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from case3.config import Settings, get_settings
from case3.eval.db import EvalDB, result_sets_equal, strip_limit
from case3.eval.metrics import (
    JudgeMetrics,
    PipelineMetrics,
    compare_vuln_classes,
    load_jsonl,
    sql_match,
    update_class_metrics,
)
from case3.judge.auditor import HybridAuditor
from case3.judge.static import StaticAnalyzer
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import load_schema_index

# Template tasks use placeholders like {number}, {date}, {name}, {from}, {to}.
# They aren't EA-evaluable without context-aware substitution, so we skip them
# from the pipeline loop and report the count separately.
_TEMPLATE_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

logger = logging.getLogger(__name__)


def run_eval(settings: Settings | None = None, limit: int | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    index = load_schema_index(settings.schema_json_path)

    all_tasks = load_jsonl(settings.dataset_tasks_path)
    vulns = load_jsonl(settings.dataset_vulns_path)
    tasks = [
        row
        for row in all_tasks
        if not _TEMPLATE_PLACEHOLDER.search(row.get("sql", ""))
        and not _TEMPLATE_PLACEHOLDER.search(row.get("task", ""))
    ]
    template_skipped = len(all_tasks) - len(tasks)
    if limit:
        tasks = tasks[:limit]
        vulns = vulns[:limit]

    pipeline_m = PipelineMetrics()
    judge_m = JudgeMetrics()
    judge_by_class: dict[str, JudgeMetrics] = {}
    static = StaticAnalyzer(schema_index=index)
    auditor = HybridAuditor(schema_index=index)

    # Result-set EA when a DB is reachable; otherwise AST/exact-string match.
    db: EvalDB | None = None
    match_mode = "ast"
    if settings.eval_database_url:
        try:
            db = EvalDB(settings.eval_database_url)
            match_mode = "result_set"
            logger.info("DB-backed eval at %s", settings.eval_database_url)
        except Exception as exc:
            logger.warning("EvalDB unavailable (%s) — falling back to AST match", exc)

    results: list[dict[str, Any]] = []
    gold_valid = 0
    gold_total_with_sql = 0

    logger.info(
        "Eval: %s pipeline tasks (%s template tasks skipped), %s vuln samples",
        len(tasks),
        template_skipped,
        len(vulns),
    )
    for i, row in enumerate(tasks, start=1):
        task = row["task"]
        gold = row.get("sql", "")
        logger.info("[%s/%s] %s", i, len(tasks), task[:80])
        result = run_sql_security_pipeline(task, schema_index=index)
        logger.info(
            "  -> approved=%s iterations=%s",
            result.approved,
            result.iterations_used,
        )
        pipeline_m.total += 1
        if result.approved:
            pipeline_m.approved += 1
        pipeline_m.total_iterations += result.iterations_used

        matched = False
        if gold:
            gold_total_with_sql += 1
            if db is not None:
                # Strip LIMIT for comparison only — audit still sees the real SQL,
                # so NO_PAGINATION findings still apply to the generator output.
                pred_res = db.fetch(strip_limit(result.final_sql))
                gold_res = db.fetch(strip_limit(gold))
                if gold_res is not None:
                    gold_valid += 1
                else:
                    logger.warning("Gold SQL failed to execute: %s", gold[:80])
                if result_sets_equal(pred_res, gold_res):
                    matched = True
            elif sql_match(result.final_sql, gold):
                matched = True
        if matched:
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
                "matched": matched,
            }
        )

    if db is not None:
        db.close()

    for row in vulns:
        sql = row["sql"]
        expected = set(row.get("expected_classes", []))
        findings = static.analyze(sql)
        predicted = {f.vuln_class for f in findings}
        compare_vuln_classes(predicted, expected, judge_m)
        update_class_metrics(predicted, expected, judge_by_class)
        # also test hybrid without llm
        audit = auditor.audit(sql)
        hybrid_predicted = {f.vuln_class for f in audit.vulnerabilities}
        compare_vuln_classes(hybrid_predicted, expected, judge_m)
        update_class_metrics(hybrid_predicted, expected, judge_by_class)

    provider = settings.resolve_llm_provider()
    _, llm_base = settings.resolve_llm_credentials()
    llm_info: dict[str, str | None] = {
        "provider": provider.value,
    }
    if provider.value == "anthropic":
        llm_info["model"] = settings.anthropic_model
        llm_info["base_url"] = None
    else:
        llm_info["model"] = settings.openai_model
        llm_info["base_url"] = llm_base

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "llm": llm_info,
        "pipeline": {
            "total": pipeline_m.total,
            "template_skipped": template_skipped,
            "dataset_size": len(all_tasks),
            "approval_rate": pipeline_m.approval_rate,
            "mean_iterations": pipeline_m.mean_iterations,
            "execution_accuracy": pipeline_m.execution_accuracy,
            "execution_accuracy_mode": match_mode,
            "gold_validity_rate": (
                gold_valid / gold_total_with_sql if gold_total_with_sql else 0.0
            ),
            "mean_risk_delta": (
                sum(pipeline_m.risk_deltas) / len(pipeline_m.risk_deltas)
                if pipeline_m.risk_deltas
                else 0.0
            ),
        },
        "judge": {
            "precision": judge_m.precision,
            "recall": judge_m.recall,
            "by_class": {
                cls: {"precision": m.precision, "recall": m.recall}
                for cls, m in sorted(judge_by_class.items())
            },
        },
        "samples": results,
    }

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out = settings.reports_dir / f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(out)
    return report
