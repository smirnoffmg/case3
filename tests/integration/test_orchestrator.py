from __future__ import annotations

from dataclasses import dataclass

from case3.config import Config
from case3.generator.base import FakeGenerator
from case3.memory import CritiqueMemory
from case3.models import ColumnInfo, Finding, SqlCandidate, TableInfo, VulnerabilityClass
from case3.orchestrator import run


@dataclass
class FakeRetriever:
    tables: list[TableInfo]

    def retrieve(self, task: str, *, k: int) -> list[TableInfo]:
        _ = task
        return self.tables[:k]


@dataclass
class FakeJudge:
    findings_by_iter: list[list[Finding]]

    def review(self, candidate: SqlCandidate, *, schema: list[TableInfo]) -> list[Finding]:
        _ = (candidate, schema)
        if not self.findings_by_iter:
            return []
        return self.findings_by_iter.pop(0)


def test_orchestrator_approves_on_first_iteration_when_no_findings() -> None:
    schema = [TableInfo(name="users", columns=[ColumnInfo(name="id", data_type="BIGINT")])]
    cfg = Config(max_iters=3)
    res = run(
        "task",
        generator=FakeGenerator("SELECT 1"),
        judges=[FakeJudge([[]])],
        memory=CritiqueMemory(),
        retriever=FakeRetriever(schema),
        full_schema=schema,
        config=cfg,
    )
    assert res.final_state == "approved"
    assert res.iterations == 1
    assert res.final_sql == "SELECT 1"


def test_orchestrator_refines_then_approves() -> None:
    schema = [TableInfo(name="users", columns=[ColumnInfo(name="id", data_type="BIGINT")])]
    cfg = Config(max_iters=3, approve_risk_threshold=4)

    bad = Finding(
        vulnerability_class=VulnerabilityClass.select_star,
        risk=5,
        explanation="overfetch",
        location=None,
        suggested_fix="select explicit columns",
        source="static",
    )
    judge = FakeJudge([[bad], []])

    res = run(
        "task",
        generator=FakeGenerator("SELECT * FROM users"),
        judges=[judge],
        memory=CritiqueMemory(),
        retriever=FakeRetriever(schema),
        full_schema=schema,
        config=cfg,
    )

    assert res.final_state == "approved"
    assert res.iterations == 2
    assert len(res.findings_per_iter) == 2
    assert len(res.lessons_per_iter) == 1


def test_orchestrator_exhausts_after_max_iters() -> None:
    schema = [TableInfo(name="users", columns=[ColumnInfo(name="id", data_type="BIGINT")])]
    cfg = Config(max_iters=2, approve_risk_threshold=4)

    bad = Finding(
        vulnerability_class=VulnerabilityClass.missing_limit,
        risk=4,
        explanation="no limit",
        location=None,
        suggested_fix="add limit",
        source="static",
    )
    judge = FakeJudge([[bad], [bad]])

    res = run(
        "task",
        generator=FakeGenerator("SELECT id FROM users"),
        judges=[judge],
        memory=CritiqueMemory(),
        retriever=FakeRetriever(schema),
        full_schema=schema,
        config=cfg,
    )

    assert res.final_state == "exhausted"
    assert res.iterations == 2
