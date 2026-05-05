from __future__ import annotations

from case3.judge.base import combine_findings
from case3.models import Finding, VulnerabilityClass


def test_combine_findings_dedups_and_keeps_max_risk() -> None:
    f1 = Finding(
        vulnerability_class=VulnerabilityClass.select_star,
        risk=5,
        explanation="short",
        location="proj",
        suggested_fix=None,
        source="static",
    )
    f2 = Finding(
        vulnerability_class=VulnerabilityClass.select_star,
        risk=7,
        explanation="much longer explanation",
        location="proj",
        suggested_fix="explicit columns",
        source="llm",
    )

    merged = combine_findings([[f1], [f2]])
    assert len(merged) == 1
    assert merged[0].risk == 7
    assert merged[0].suggested_fix == "explicit columns"
    assert merged[0].explanation == "much longer explanation"
    assert merged[0].source == "llm"
