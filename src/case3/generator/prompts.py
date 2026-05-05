from __future__ import annotations

from case3.models import CritiqueLesson, TableInfo

SYSTEM_PROMPT = """You are a PostgreSQL SQL generator.\n\nReturn ONLY valid JSON with keys: sql, rationale.\nNever return markdown, code fences, or explanations outside JSON.\n""".strip()


def render_schema_context(schema: list[TableInfo]) -> str:
    lines: list[str] = ["Schema context (tables and columns):"]
    for t in schema:
        cols = ", ".join(f"{c.name}:{c.data_type}" for c in t.columns)
        lines.append(f"- {t.name}({cols})")
    return "\n".join(lines)


def render_lessons(lessons: list[CritiqueLesson]) -> str:
    if not lessons:
        return "Learned lessons: (none)"
    lines: list[str] = ["Avoid these patterns (learned from previous iterations):"]
    for lesson in lessons:
        lines.append(f"- Avoid: {lesson.pattern_to_avoid} | Instead: {lesson.correct_approach}")
    return "\n".join(lines)


def build_prompt(*, task: str, schema: list[TableInfo], lessons: list[CritiqueLesson]) -> str:
    parts = [
        SYSTEM_PROMPT,
        render_schema_context(schema),
        render_lessons(lessons),
        f"Task: {task}",
    ]
    return "\n\n".join(parts).strip() + "\n"
