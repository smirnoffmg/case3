from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.fake import FakeListLLM

from case3.judge.llm import LlmJudge
from case3.models import ColumnInfo, SqlCandidate, TableInfo, VulnerabilityClass


@dataclass
class RecordingInvoker:
    inner: FakeListLLM
    last_prompt: str = ""

    def invoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return str(self.inner.invoke(prompt))


def test_llm_judge_parses_findings_json_list() -> None:
    llm = RecordingInvoker(
        FakeListLLM(
            responses=[
                """[
                  {"vulnerability_class":"select_star","risk":5,"explanation":"overfetch","location":null,"suggested_fix":"select explicit"},
                  {"vulnerability_class":"missing_limit","risk":4,"explanation":"no limit","location":"end","suggested_fix":null}
                ]"""
            ]
        )
    )
    judge = LlmJudge(llm=llm)

    schema = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
            ],
        )
    ]
    cand = SqlCandidate(sql="SELECT * FROM users", iteration=0)
    findings = judge.review(cand, schema=schema)

    assert {f.vulnerability_class for f in findings} == {
        VulnerabilityClass.select_star,
        VulnerabilityClass.missing_limit,
    }
    assert all(f.source == "llm" for f in findings)
    assert "SQL:" in llm.last_prompt


def test_llm_judge_returns_empty_on_invalid_json() -> None:
    llm = RecordingInvoker(FakeListLLM(responses=["not json"]))
    judge = LlmJudge(llm=llm)

    cand = SqlCandidate(sql="SELECT 1", iteration=0)
    findings = judge.review(cand, schema=[])
    assert findings == []
