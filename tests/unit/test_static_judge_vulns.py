from __future__ import annotations

import json
from pathlib import Path

import pytest

from case3.judge.static import StaticJudge
from case3.models import ColumnInfo, SqlCandidate, TableInfo, VulnerabilityClass


def _load_cases() -> list[dict[str, object]]:
    path = Path("data/examples/vulns.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: str(c["id"]))
def test_static_judge_detects_expected_vuln_classes(case: dict[str, object]) -> None:
    schema = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
                ColumnInfo(name="email", data_type="TEXT"),
                ColumnInfo(name="password_hash", data_type="TEXT", is_sensitive=True),
            ],
        )
    ]

    judge = StaticJudge()
    candidate = SqlCandidate(sql=str(case["sql"]), iteration=0)
    findings = judge.review(candidate, schema=schema)
    got = {f.vulnerability_class for f in findings}

    expect_raw = case["expect"]
    assert isinstance(expect_raw, list)
    expect = {VulnerabilityClass(str(v)) for v in expect_raw}
    assert expect.issubset(got)
