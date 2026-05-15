from case3.config import get_settings
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import load_schema_index, to_baseline_dict


def test_pipeline_stub_approves_safe_query():
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
        generator_kwargs={"force_stub": True},
        auditor_kwargs={"use_llm": False},
    )
    assert result.final_sql
    assert result.iterations_used >= 1
    assert "LIMIT" in result.final_sql.upper()
