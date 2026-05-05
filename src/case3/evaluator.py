from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from case3.config import Config
from case3.generator.base import Generator
from case3.judge.base import Judge
from case3.memory import CritiqueMemory
from case3.models import RunResult, TableInfo
from case3.orchestrator import run
from case3.schema_index.parser import parse_ddl
from case3.schema_index.retriever import Bm25SchemaRetriever


@dataclass(frozen=True)
class Metrics:
    avg_iterations: float
    avg_max_risk: float
    repeated_classes_rate: float


def max_risk_per_iter(result: RunResult) -> list[int]:
    return [max((f.risk for f in findings), default=0) for findings in result.findings_per_iter]


def repeated_classes_between_iters(result: RunResult) -> int:
    count = 0
    for a, b in zip(result.findings_per_iter, result.findings_per_iter[1:], strict=False):
        ca = {f.vulnerability_class for f in a}
        cb = {f.vulnerability_class for f in b}
        count += len(ca.intersection(cb))
    return count


def aggregate_metrics(results: list[RunResult]) -> Metrics:
    if not results:
        return Metrics(avg_iterations=0.0, avg_max_risk=0.0, repeated_classes_rate=0.0)

    avg_iterations = sum(r.iterations for r in results) / len(results)
    avg_max_risk = sum(sum(max_risk_per_iter(r)) / max(r.iterations, 1) for r in results) / len(
        results
    )

    repeated = sum(repeated_classes_between_iters(r) for r in results)
    transitions = sum(max(r.iterations - 1, 0) for r in results)
    repeated_rate = (repeated / transitions) if transitions else 0.0

    return Metrics(
        avg_iterations=avg_iterations,
        avg_max_risk=avg_max_risk,
        repeated_classes_rate=repeated_rate,
    )


def load_tasks(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_schema(*, ddl_path: Path) -> list[TableInfo]:
    ddl = ddl_path.read_text(encoding="utf-8")
    return parse_ddl(ddl, sensitivity={})


def evaluate(
    *,
    tasks_path: Path,
    ddl_path: Path,
    generator: Generator,
    judges: list[Judge],
) -> Metrics:
    full_schema = load_schema(ddl_path=ddl_path)
    retriever = Bm25SchemaRetriever(full_schema)

    results: list[RunResult] = []
    for t in load_tasks(tasks_path):
        task = str(t["task"])
        raw_max_iters = t.get("max_iters", 4)
        max_iters = int(raw_max_iters) if isinstance(raw_max_iters, (int, str)) else 4
        cfg = Config(max_iters=max_iters)
        res = run(
            task,
            generator=generator,
            judges=judges,
            memory=CritiqueMemory(),
            retriever=retriever,
            full_schema=full_schema,
            config=cfg,
        )
        results.append(res)

    return aggregate_metrics(results)
