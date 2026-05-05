from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.fake import FakeListLLM

from case3.generator.prompt_rag import PromptRagGenerator
from case3.models import ColumnInfo, CritiqueLesson, TableInfo


@dataclass
class RecordingInvoker:
    inner: FakeListLLM
    last_prompt: str = ""

    def invoke(self, prompt: str) -> str:
        self.last_prompt = prompt
        return str(self.inner.invoke(prompt))


def test_prompt_rag_generator_builds_prompt_with_schema_and_lessons() -> None:
    llm = RecordingInvoker(
        FakeListLLM(
            responses=[
                '{"sql":"SELECT id FROM users LIMIT 1","rationale":"ok"}',
            ]
        )
    )
    gen = PromptRagGenerator(llm=llm)

    schema = [
        TableInfo(
            name="users",
            columns=[
                ColumnInfo(name="id", data_type="BIGINT"),
                ColumnInfo(name="email", data_type="TEXT"),
            ],
        )
    ]
    lessons = [
        CritiqueLesson(
            pattern_to_avoid="SELECT *",
            correct_approach="Select explicit columns",
            severity=5,
            seen_count=1,
        )
    ]

    cand = gen.generate("Get first user id", schema=schema, lessons=lessons, iteration=2)
    assert cand.sql.startswith("SELECT id FROM users")
    assert cand.iteration == 2

    assert "users(id:BIGINT, email:TEXT)" in llm.last_prompt
    assert "Avoid: SELECT *" in llm.last_prompt
    assert "Task: Get first user id" in llm.last_prompt
