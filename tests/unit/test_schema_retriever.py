from __future__ import annotations

from case3.models import ColumnInfo, TableInfo
from case3.schema_index.retriever import Bm25SchemaRetriever


def test_bm25_retriever_recall_at_2_is_1_on_toy_schema() -> None:
    tables = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
                ColumnInfo(name="email", data_type="TEXT"),
                ColumnInfo(name="password_hash", data_type="TEXT", is_sensitive=True),
            ],
        ),
        TableInfo(
            name="orders",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
                ColumnInfo(name="user_id", data_type="BIGINT"),
                ColumnInfo(name="total_cents", data_type="BIGINT"),
            ],
        ),
        TableInfo(
            name="products",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
                ColumnInfo(name="sku", data_type="TEXT"),
                ColumnInfo(name="price_cents", data_type="BIGINT"),
            ],
        ),
    ]

    retriever = Bm25SchemaRetriever(tables)

    cases: list[tuple[str, str]] = [
        ("Find user by email", "users"),
        ("Total amount by user id", "orders"),
        ("Show product price by sku", "products"),
    ]

    for task, expected in cases:
        top = retriever.retrieve(task, k=2)
        assert any(t.name == expected for t in top)
