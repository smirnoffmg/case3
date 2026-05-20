"""RAG-based SQL generator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from case3.config import Settings, get_settings
from case3.contracts import SQLGenerator
from case3.generator.prompts import (
    build_initial_prompt,
    build_repair_prompt,
    format_schema_context,
)
from case3.llm.client import LLMClient, get_llm_client
from case3.models import AuditResult
from case3.schema_index.loader import load_schema_index
from case3.schema_index.parser import SchemaIndex
from case3.schema_index.retriever import SchemaRetriever


def extract_sql(text: str) -> str:
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # last resort: find SELECT/INSERT/UPDATE/DELETE statement
    m = re.search(
        r"((?:SELECT|INSERT|UPDATE|DELETE|WITH)\b[\s\S]+?)(?:;|\Z)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return text.strip()


def load_few_shot(path: Path) -> str:
    if not path.is_file():
        return ""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    parts: list[str] = []
    for ex in data.get("safe", [])[:6]:
        parts.append(f"Example (safe): {ex.get('task')}\n```sql\n{ex.get('sql')}\n```")
    return "\n".join(parts)


class PromptRAGGenerator(SQLGenerator):
    def __init__(
        self,
        llm: LLMClient | None = None,
        settings: Settings | None = None,
        schema_index: SchemaIndex | None = None,
        lessons: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings or get_settings()
        self._llm = llm or get_llm_client(self._settings)
        self._lessons = lessons or []
        if schema_index is not None:
            self._index = schema_index
        else:
            try:
                self._index = load_schema_index(self._settings.schema_json_path)
            except FileNotFoundError:
                from case3.schema_index.parser import build_schema_index

                self._index = build_schema_index(self._settings.schema_ddl_path)
        self._retriever = SchemaRetriever(self._index)
        self._few_shot = load_few_shot(self._settings.few_shot_path)

    def set_lessons(self, lessons: list[str]) -> None:
        self._lessons = lessons

    def generate(
        self,
        task_description: str,
        sql_history: list[str] | None = None,
        audit_feedback: AuditResult | None = None,
        iteration: int = 1,
    ) -> str:
        tables = self._retriever.retrieve(task_description, top_k=self._settings.retriever_top_k)
        schema_ctx = format_schema_context(tables)
        if tables:
            schema_ctx = f"public.{tables[0].name}\n" + schema_ctx

        if iteration > 1 and audit_feedback is not None:
            prompt = build_repair_prompt(
                task_description,
                sql_history or [],
                audit_feedback,
                self._lessons,
                schema_ctx,
            )
        else:
            prompt = build_initial_prompt(task_description, schema_ctx, self._few_shot)

        raw = self._llm.complete(prompt)
        return extract_sql(raw)
