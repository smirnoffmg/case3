from case3.schema_index.parser import parse_ddl

FIXTURE = """
CREATE TABLE public.foo (id bigint, name varchar(100));
COMMENT ON TABLE public.foo IS 'Foo table';
COMMENT ON COLUMN public.foo.name IS 'Name';
"""


def test_parse_tables_and_comments():
    index = parse_ddl(FIXTURE)
    assert "foo" in index.tables
    assert index.tables["foo"].comment == "Foo table"
    assert any(c.name == "name" for c in index.tables["foo"].columns)
