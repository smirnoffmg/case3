from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from case3.models import Finding, SqlCandidate, TableInfo, VulnerabilityClass


class LlmInvoker(Protocol):
    def invoke(self, prompt: str) -> str: ...


SYSTEM_PROMPT = """You are a SQL security auditor for PostgreSQL.

Given a SQL query, return ONLY valid JSON: an array of findings.
Each finding must have keys:
- vulnerability_class: one of the allowed classes
- risk: integer 0..10
- explanation: string
- location: string|null
- suggested_fix: string|null

Return [] if no issues.
Never return markdown or code fences.
""".strip()


def _schema_context(schema: list[TableInfo]) -> str:
    lines: list[str] = ["Schema (sensitive columns are marked):"]
    for t in schema:
        cols = ", ".join(
            f"{c.name}{'(!)' if c.is_sensitive else ''}:{c.data_type}" for c in t.columns
        )
        lines.append(f"- {t.name}({cols})")
    return "\n".join(lines)


def _build_prompt(candidate: SqlCandidate, *, schema: list[TableInfo]) -> str:
    return (
        "\n\n".join(
            [
                SYSTEM_PROMPT,
                _schema_context(schema),
                f"SQL:\n{candidate.sql.strip()}",
            ]
        ).strip()
        + "\n"
    )


class LlmJudge:
    def __init__(self, *, llm: LlmInvoker):
        self._llm = llm

    def review(self, candidate: SqlCandidate, *, schema: list[TableInfo]) -> list[Finding]:
        prompt = _build_prompt(candidate, schema=schema)
        raw = self._llm.invoke(prompt)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        findings: list[Finding] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                findings.append(
                    Finding(
                        vulnerability_class=VulnerabilityClass(
                            str(item.get("vulnerability_class", ""))
                        ),
                        risk=int(item.get("risk", 0)),
                        explanation=str(item.get("explanation", "")).strip(),
                        location=None
                        if item.get("location") is None
                        else str(item.get("location")),
                        suggested_fix=None
                        if item.get("suggested_fix") is None
                        else str(item.get("suggested_fix")),
                        source="llm",
                    )
                )
            except (ValueError, ValidationError):
                continue

        return findings
