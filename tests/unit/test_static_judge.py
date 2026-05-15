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


def test_sensitive_columns(mini_db_schema):
    findings = StaticAnalyzer().analyze(
        "SELECT id, email FROM public.sys_employee LIMIT 10",
        mini_db_schema,
    )
    assert any(f.vuln_class == "DIRECT_SENSITIVE" for f in findings)


def test_plpgsql_unsafe():
    findings = StaticAnalyzer().analyze("EXECUTE format('SELECT %I', 'x');")
    assert any(f.vuln_class == "PLPGSQL_UNSAFE" for f in findings)
