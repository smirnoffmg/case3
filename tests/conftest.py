"""Pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.schema_index.parser import build_schema_index, parse_ddl

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DDL = """
CREATE TABLE public.sys_employee (
    id bigint NOT NULL,
    name character varying(2000),
    email character varying(2000),
    phone character varying(100),
    status smallint
);
COMMENT ON TABLE public.sys_employee IS 'Employees';
COMMENT ON COLUMN public.sys_employee.email IS 'E-MAIL';
CREATE TABLE public.acc_number (
    id bigint NOT NULL,
    account_name character varying(2000)
);
"""


@pytest.fixture
def mini_schema():
    return parse_ddl(FIXTURE_DDL)


@pytest.fixture
def mini_schema_pii(mini_schema):
    from case3.schema_index.pii import mark_sensitive_columns

    mark_sensitive_columns(mini_schema)
    return mini_schema


@pytest.fixture
def schema_index_built(tmp_path):
    ddl = tmp_path / "test.sql"
    ddl.write_text(FIXTURE_DDL, encoding="utf-8")
    return build_schema_index(ddl)
