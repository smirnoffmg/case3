"""Main pipeline entrypoint."""

from __future__ import annotations

from typing import Any

from case3.config import Settings, get_settings
from case3.contracts import SQLSecuritySystem
from case3.generator.prompt_rag import PromptRAGGenerator
from case3.judge.auditor import HybridAuditor
from case3.llm.client import get_llm_client
from case3.models import SystemResult
from case3.orchestrator.system import Orchestrator
from case3.schema_index.loader import load_schema_index, to_baseline_dict


def run_sql_security_pipeline(
    task_description: str,
    db_schema: dict[str, Any] | None = None,
    max_iterations: int | None = None,
    timeout_sec: float | None = None,
    settings_override: Settings | None = None,
    generator_kwargs: dict[str, Any] | None = None,
    auditor_kwargs: dict[str, Any] | None = None,
) -> SystemResult:
    settings = settings_override or get_settings()
    gen_kw = dict(generator_kwargs or {})
    aud_kw = dict(auditor_kwargs or {})

    if db_schema is None:
        index = load_schema_index(settings.schema_json_path)
        db_schema = to_baseline_dict(index)

    llm = get_llm_client(settings)
    generator = PromptRAGGenerator(db_schema=db_schema, llm=llm, settings=settings, **gen_kw)
    auditor = HybridAuditor(llm=llm, settings=settings, **aud_kw)
    system: SQLSecuritySystem = Orchestrator(
        generator=generator,
        auditor=auditor,
        max_iterations=max_iterations or settings.max_iterations,
        timeout_sec=timeout_sec if timeout_sec is not None else settings.timeout_sec,
        llm=llm,
    )
    result = system.run(task_description)
    result.metadata["llm_mode"] = settings.llm_endpoint_label()
    return result
