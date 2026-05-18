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


def test_not_stuck_after_one_iteration():
    mem = FeedbackMemory()
    mem.update(_audit(["DIRECT_SENSITIVE"]), 1)
    assert not mem.is_stuck()


def test_stuck_when_same_classes_repeat():
    mem = FeedbackMemory()
    mem.update(_audit(["DIRECT_SENSITIVE"]), 1)
    mem.update(_audit(["DIRECT_SENSITIVE"]), 2)
    assert mem.is_stuck()


def test_not_stuck_when_classes_change():
    mem = FeedbackMemory()
    mem.update(_audit(["DIRECT_SENSITIVE", "SELECT_STAR"]), 1)
    mem.update(_audit(["DIRECT_SENSITIVE"]), 2)
    assert not mem.is_stuck()


def test_stuck_requires_min_iterations():
    mem = FeedbackMemory()
    mem.update(_audit(["DIRECT_SENSITIVE"]), 1)
    mem.update(_audit(["DIRECT_SENSITIVE"]), 2)
    mem.update(_audit(["DIRECT_SENSITIVE"]), 3)
    assert mem.is_stuck(min_iterations=3)
    assert not mem.is_stuck(min_iterations=4)
