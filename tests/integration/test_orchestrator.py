from case3.config import get_settings
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import load_schema_index, to_baseline_dict


def test_pipeline_approves_safe_query():
    settings = get_settings()
    try:
        index = load_schema_index(settings.schema_json_path)
    except FileNotFoundError:
        from case3.schema_index.parser import build_schema_index

        index = build_schema_index(settings.schema_ddl_path)
    db_schema = to_baseline_dict(index)

    result = run_sql_security_pipeline(
        "Список сотрудников с id и именем",
        db_schema=db_schema,
    )
    assert result.final_sql
    assert result.iterations_used >= 1
    assert "LIMIT" in result.final_sql.upper()
    assert result.approved


def test_pipeline_refuses_destructive_task():
    result = run_sql_security_pipeline(
        "Удалить каждого третьего сотрудника",
    )
    assert not result.approved
    assert "Отказ" in result.final_sql
    assert result.iterations_used == 1


def test_pipeline_refuses_greeting_task():
    result = run_sql_security_pipeline("Привет!")
    assert not result.approved
    assert result.iterations_used == 1
    assert result.metadata.get("refusal") == "non_actionable_task"
    assert "Отказ" in result.final_sql
    assert "SELECT" not in result.final_sql.upper() or result.final_sql.strip().startswith("--")
    assert any(
        v.vuln_class == "TASK_NOT_ACTIONABLE" for v in result.iterations_log[0].audit_result.vulnerabilities
    )


def test_pipeline_accepts_greeting_with_query():
    settings = get_settings()
    try:
        index = load_schema_index(settings.schema_json_path)
    except FileNotFoundError:
        from case3.schema_index.parser import build_schema_index

        index = build_schema_index(settings.schema_ddl_path)
    db_schema = to_baseline_dict(index)

    result = run_sql_security_pipeline(
        "Привет! Список сотрудников с id и именем, лимит 10",
        db_schema=db_schema,
    )
    assert result.metadata.get("refusal") != "non_actionable_task"
    assert result.final_sql
    assert "LIMIT" in result.final_sql.upper()
    assert result.approved
