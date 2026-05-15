from case3.schema_index.retriever import SchemaRetriever


def test_retrieve_employee_table(mini_schema):
    r = SchemaRetriever(mini_schema)
    hits = r.retrieve("список сотрудников email", top_k=3)
    assert hits
    names = {h.name for h in hits}
    assert "sys_employee" in names
