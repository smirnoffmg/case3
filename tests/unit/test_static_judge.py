from case3.judge.static import StaticAnalyzer


def test_select_star():
    findings = StaticAnalyzer().analyze("SELECT * FROM public.sys_employee")
    classes = {f.vuln_class for f in findings}
    assert "SELECT_STAR" in classes


def test_dml_no_where():
    findings = StaticAnalyzer().analyze("DELETE FROM public.acc_number")
    assert any(f.vuln_class == "DML_NO_WHERE" for f in findings)


def test_no_pagination():
    findings = StaticAnalyzer().analyze("SELECT id, name FROM public.sys_employee WHERE status = 1")
    assert any(f.vuln_class == "NO_PAGINATION" for f in findings)


def test_sql_injection_classic():
    findings = StaticAnalyzer().analyze("SELECT id FROM t WHERE name = '' || user_input || ''")
    assert any(f.vuln_class == "SQL_INJ_CLASSIC" for f in findings)


def test_pg_sleep():
    findings = StaticAnalyzer().analyze("SELECT pg_sleep(5)")
    assert any(f.vuln_class == "SQL_INJ_TIME" for f in findings)


def test_sensitive_columns(mini_schema_pii):
    findings = StaticAnalyzer(schema_index=mini_schema_pii).analyze(
        "SELECT id, email FROM public.sys_employee LIMIT 10",
    )
    assert any(f.vuln_class == "DIRECT_SENSITIVE" for f in findings)


def test_plpgsql_unsafe():
    findings = StaticAnalyzer().analyze("EXECUTE format('SELECT %I', 'x');")
    assert any(f.vuln_class == "PLPGSQL_UNSAFE" for f in findings)


def test_sql_inj_union_plain():
    # canonical UNION injection — no concatenation required
    findings = StaticAnalyzer().analyze(
        "SELECT id FROM users WHERE id = 1 UNION SELECT password FROM users"
    )
    assert any(f.vuln_class == "SQL_INJ_UNION" for f in findings)


def test_sql_inj_union_all():
    # UNION ALL variant must also be caught
    findings = StaticAnalyzer().analyze(
        "SELECT id FROM orders UNION ALL SELECT credit_card FROM payments"
    )
    assert any(f.vuln_class == "SQL_INJ_UNION" for f in findings)
