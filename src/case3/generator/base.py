from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from case3.models import CritiqueLesson, SqlCandidate, TableInfo


class Generator(Protocol):
    def generate(
        self,
        task: str,
        *,
        schema: list[TableInfo],
        lessons: list[CritiqueLesson],
        iteration: int,
    ) -> SqlCandidate: ...


@dataclass(frozen=True)
class FakeGenerator:
    sql: str

    def generate(
        self,
        task: str,
        *,
        schema: list[TableInfo],
        lessons: list[CritiqueLesson],
        iteration: int,
    ) -> SqlCandidate:
        _ = (task, schema, lessons)
        return SqlCandidate(sql=self.sql, rationale="fake", iteration=iteration)
