from case3.contracts import is_approved
from case3.judge.auditor import HybridAuditor
from case3.judge.policy import (
    analyze_task_policy,
    sql_contains_destructive_dml,
    task_requests_destruction,
)


def test_destructive_task_russian():
    assert task_requests_destruction("Удалить каждого третьего сотрудника")


def test_safe_task():
    assert not task_requests_destruction("Список сотрудников с email, лимит 10")


def test_destructive_sql_detected():
    assert sql_contains_destructive_dml("DELETE FROM public.sys_employee WHERE id % 3 = 0")


def test_policy_rejects_mismatch():
    findings = analyze_task_policy(
        "Удалить каждого третьего сотрудника",
        "SELECT id, name FROM public.sys_employee LIMIT 10",
    )
    assert any(f.vuln_class == "TASK_DESTRUCTIVE" for f in findings)
    assert not is_approved(max(f.risk_score for f in findings), findings)


def test_refusal_comment_not_approved():
    audit = HybridAuditor().audit(
        "-- Отказ: деструктивные операции не поддерживаются.",
        task_description="Дай список всех транзакций",
    )
    assert not audit.approved
    assert any(v.vuln_class == "NOT_VALID_SELECT" for v in audit.vulnerabilities)


def test_hybrid_auditor_with_task():
    audit = HybridAuditor().audit(
        "SELECT id FROM public.sys_employee LIMIT 10",
        task_description="Удалить всех сотрудников",
    )
    assert not audit.approved
    assert any(v.vuln_class == "TASK_DESTRUCTIVE" for v in audit.vulnerabilities)
