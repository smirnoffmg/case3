from __future__ import annotations

from case3.schema_index.parser import parse_ddl


def test_parse_ddl_extracts_tables_columns_and_fk_and_sensitivity() -> None:
    ddl = """
    CREATE TABLE users (
      id BIGINT PRIMARY KEY,
      email TEXT NOT NULL,
      password_hash TEXT NOT NULL
    );

    CREATE TABLE orders (
      id BIGINT PRIMARY KEY,
      user_id BIGINT NOT NULL,
      total_cents BIGINT NOT NULL,
      CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    tables = parse_ddl(ddl, sensitivity={"password_hash": True})

    by_name = {t.name: t for t in tables}
    assert set(by_name.keys()) == {"users", "orders"}

    users = by_name["users"]
    assert [c.name for c in users.columns] == ["id", "email", "password_hash"]
    assert [c.is_sensitive for c in users.columns if c.name == "password_hash"] == [True]

    orders = by_name["orders"]
    assert len(orders.foreign_keys) == 1
    fk = orders.foreign_keys[0]
    assert fk.column == "user_id"
    assert fk.ref_table == "users"
    assert fk.ref_column == "id"
