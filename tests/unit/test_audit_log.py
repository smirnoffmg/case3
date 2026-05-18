from datetime import UTC, datetime

from case3.audit.log_builder import build_audit_log
from case3.models import AuditResult, IterationLog, Vulnerability


def _iteration(
    risk: float, approved: bool, vulns: list[Vulnerability] | None = None
) -> IterationLog:
    return IterationLog(
        timestamp=datetime.now(UTC),
        iteration=1,
        sql_query="SELECT id FROM t LIMIT 10",
        audit_result=AuditResult(
            approved=approved,
            vulnerabilities=vulns or [],
            overall_risk_score=risk,
            summary="",
        ),
    )


def test_approved_log_shows_risk_and_threshold():
    log = build_audit_log(
        task="List employees",
        iterations_log=[_iteration(risk=3.2, approved=True)],
        final_sql="SELECT id FROM t LIMIT 10",
        approved=True,
        risk_threshold=4.0,
        hard_block_risk=8.0,
    )
    assert "3.2" in log
    assert "4.0" in log


def test_rejected_log_shows_risk_exceeded_threshold():
    log = build_audit_log(
        task="List employees",
        iterations_log=[_iteration(risk=6.5, approved=False)],
        final_sql="SELECT * FROM t",
        approved=False,
        risk_threshold=4.0,
        hard_block_risk=8.0,
    )
    assert "6.5" in log
    assert "4.0" in log


def test_rejected_log_shows_hard_block_class():
    vuln = Vulnerability(
        vuln_class="SQL_INJ_UNION",
        risk_score=9.0,
        description="UNION injection detected",
        recommendation="Remove UNION",
    )
    log = build_audit_log(
        task="List employees",
        iterations_log=[_iteration(risk=9.0, approved=False, vulns=[vuln])],
        final_sql="SELECT 1 UNION SELECT password FROM users",
        approved=False,
        risk_threshold=4.0,
        hard_block_risk=8.0,
    )
    assert "SQL_INJ_UNION" in log
    assert "8.0" in log
