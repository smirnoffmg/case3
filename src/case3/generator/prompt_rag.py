from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from case3.generator.prompts import build_prompt
from case3.models import CritiqueLesson, SqlCandidate, TableInfo


class LlmInvoker(Protocol):
    def invoke(self, prompt: str) -> str: ...


class PromptRagGenerator:
    def __init__(self, *, llm: LlmInvoker):
        self._llm = llm

    def generate(
        self,
        task: str,
        *,
        schema: list[TableInfo],
        lessons: list[CritiqueLesson],
        iteration: int,
    ) -> SqlCandidate:
        prompt = build_prompt(task=task, schema=schema, lessons=lessons)
        raw = self._llm.invoke(prompt)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                "LLM returned non-JSON; expected strict JSON with keys sql, rationale."
            ) from e

        try:
            return SqlCandidate(
                sql=str(payload.get("sql", "")).strip(),
                rationale=str(payload.get("rationale", "")).strip(),
                iteration=iteration,
            )
        except ValidationError as e:
            raise ValueError("LLM JSON did not match SqlCandidate contract.") from e
