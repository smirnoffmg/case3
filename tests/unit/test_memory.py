from __future__ import annotations

from case3.memory import CritiqueMemory
from case3.models import Finding, VulnerabilityClass


def test_memory_distill_dedups_and_increments_seen_count() -> None:
    mem = CritiqueMemory()

    f1 = Finding(
        vulnerability_class=VulnerabilityClass.select_star,
        risk=5,
        explanation="overfetch",
        location=None,
        suggested_fix="select explicit columns",
        source="static",
    )
    f2 = Finding(
        vulnerability_class=VulnerabilityClass.select_star,
        risk=7,
        explanation="still overfetch",
        location=None,
        suggested_fix="select explicit columns",
        source="llm",
    )

    first = mem.distill([f1])
    assert len(first) == 1
    assert first[0].seen_count == 1
    assert first[0].severity == 5

    second = mem.distill([f2])
    assert len(second) == 0  # dedup, but updates existing

    lessons = mem.lessons()
    assert len(lessons) == 1
    assert lessons[0].seen_count == 2
    assert lessons[0].severity == 7
