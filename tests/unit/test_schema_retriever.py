import pytest

from case3.schema_index.parser import ColumnInfo, SchemaIndex, TableInfo
from case3.schema_index.retriever import SchemaRetriever


@pytest.fixture
def fk_schema() -> SchemaIndex:
    """Two tables linked by a FK: sys_employee.org_id → org.id"""
    return SchemaIndex(
        tables={
            "sys_employee": TableInfo(
                name="sys_employee",
                comment="Employees",
                columns=[
                    ColumnInfo(name="id", data_type="bigint"),
                    ColumnInfo(name="name", data_type="varchar"),
                    ColumnInfo(name="org_id", data_type="bigint"),
                ],
            ),
            "org": TableInfo(
                name="org",
                comment="Organisations",
                columns=[
                    ColumnInfo(name="id", data_type="bigint"),
                    ColumnInfo(name="name", data_type="varchar"),
                ],
            ),
            "unrelated": TableInfo(
                name="unrelated",
                comment="Unrelated table",
                columns=[ColumnInfo(name="id", data_type="bigint")],
            ),
        },
        fk_edges=[("sys_employee", "org_id", "org", "id")],
    )


def test_retrieve_employee_table_russian(mini_schema):
    r = SchemaRetriever(mini_schema)
    hits = r.retrieve("список сотрудников email", top_k=3)
    assert hits
    assert "sys_employee" in {h.name for h in hits}


def test_retrieve_employee_table_english(mini_schema):
    # BM25 must find sys_employee even when the task is in English
    r = SchemaRetriever(mini_schema)
    hits = r.retrieve("list employees with name and email", top_k=3)
    assert hits
    assert hits[0].name == "sys_employee"


def test_retrieve_account_table_english(mini_schema):
    r = SchemaRetriever(mini_schema)
    hits = r.retrieve("account number details", top_k=3)
    assert hits
    assert "acc_number" in {h.name for h in hits}


def test_fk_neighbor_added_when_bm25_retrieves_source(fk_schema):
    # BM25 finds sys_employee; FK expansion must pull in org
    r = SchemaRetriever(fk_schema)
    hits = r.retrieve("список сотрудников", top_k=1)
    names = {h.name for h in hits}
    assert "sys_employee" in names
    assert "org" in names


def test_fk_neighbor_added_when_bm25_retrieves_target(fk_schema):
    # BM25 finds org; FK expansion must pull in sys_employee
    r = SchemaRetriever(fk_schema)
    hits = r.retrieve("organisations", top_k=1)
    names = {h.name for h in hits}
    assert "org" in names
    assert "sys_employee" in names


def test_fk_neighbor_not_duplicated(fk_schema):
    # When both tables score well, FK expansion must not add duplicates
    r = SchemaRetriever(fk_schema)
    hits = r.retrieve("employee organisation", top_k=2)
    assert len([h for h in hits if h.name == "org"]) == 1
    assert len([h for h in hits if h.name == "sys_employee"]) == 1


def test_unrelated_table_not_pulled_by_fk(fk_schema):
    r = SchemaRetriever(fk_schema)
    hits = r.retrieve("список сотрудников", top_k=1)
    assert "unrelated" not in {h.name for h in hits}
