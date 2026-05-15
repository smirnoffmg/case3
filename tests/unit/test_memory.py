from case3.memory.feedback import FeedbackMemory
from case3.models import AuditResult, Vulnerability


def _audit(classes: list[str]) -> AuditResult:
    vulns = [
        Vulnerability(
            vuln_class=c,
            risk_score=5.0,
            description="d",
            recommendation="r",
        )
        for c in classes
    ]
    overall = max((v.risk_score for v in vulns), default=0.0)
    return AuditResult(
        approved=False,
        vulnerabilities=vulns,
        overall_risk_score=overall,
        summary="",
    )


def test_regression_detection():
    mem = FeedbackMemory()
    mem.update(_audit(["SELECT_STAR"]), 1)
    mem.update(_audit([]), 2)
    assert mem.detect_regression(_audit(["SELECT_STAR"]))
