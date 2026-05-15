from case3.schema_index.pii import mark_sensitive_columns


def test_marks_email_sensitive(mini_schema):
    mark_sensitive_columns(mini_schema)
    emp = mini_schema.tables["sys_employee"]
    email_col = next(c for c in emp.columns if c.name == "email")
    assert email_col.sensitive is True
