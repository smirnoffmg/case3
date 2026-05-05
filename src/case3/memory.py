from __future__ import annotations

from dataclasses import dataclass

from case3.models import CritiqueLesson, Finding


@dataclass
class CritiqueMemory:
    """
    KISS in-memory memory store for one run.
    Distills Findings into de-duplicated lessons that can be injected as negative few-shot.
    """

    _lessons: dict[str, CritiqueLesson]

    def __init__(self) -> None:
        self._lessons = {}

    def lessons(self) -> list[CritiqueLesson]:
        return list(self._lessons.values())

    def distill(self, findings: list[Finding]) -> list[CritiqueLesson]:
        new_lessons: list[CritiqueLesson] = []
        for f in findings:
            key = (
                f"{f.vulnerability_class.value}:{f.suggested_fix or ''}:{f.location or ''}".strip()
            )

            pattern = f.vulnerability_class.value
            correct = f.suggested_fix or "Apply safer query patterns and parameterization."

            existing = self._lessons.get(key)
            if existing is None:
                lesson = CritiqueLesson(
                    pattern_to_avoid=pattern,
                    correct_approach=correct,
                    severity=f.risk,
                    seen_count=1,
                )
                self._lessons[key] = lesson
                new_lessons.append(lesson)
            else:
                self._lessons[key] = existing.model_copy(
                    update={
                        "severity": max(existing.severity, f.risk),
                        "seen_count": existing.seen_count + 1,
                    }
                )

        return new_lessons
