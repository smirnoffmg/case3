from __future__ import annotations

from typing import Protocol

from case3.models import Finding, SqlCandidate, TableInfo


class Judge(Protocol):
    def review(self, candidate: SqlCandidate, *, schema: list[TableInfo]) -> list[Finding]: ...


def combine_findings(findings_lists: list[list[Finding]]) -> list[Finding]:
    """
    KISS: deterministic merge.
    - Deduplicate by (vulnerability_class, location) regardless of source.
    - Keep the max risk; prefer longer explanation/suggested_fix when present.
    """
    merged: dict[tuple[object, object], Finding] = {}
    for findings in findings_lists:
        for f in findings:
            key = (f.vulnerability_class, f.location)
            prev = merged.get(key)
            if prev is None:
                merged[key] = f
                continue

            risk = max(prev.risk, f.risk)
            explanation = (
                prev.explanation if len(prev.explanation) >= len(f.explanation) else f.explanation
            )
            suggested_fix = prev.suggested_fix or f.suggested_fix
            source = prev.source if prev.risk >= f.risk else f.source
            merged[key] = prev.model_copy(
                update={
                    "risk": risk,
                    "explanation": explanation,
                    "suggested_fix": suggested_fix,
                    "source": source,
                }
            )

    # stable ordering for reports/tests
    return sorted(
        merged.values(),
        key=lambda x: (x.vulnerability_class.value, x.location or "", -x.risk, x.source),
    )
