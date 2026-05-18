"""Offline evaluation metrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def normalize_sql(sql: str) -> str:
    s = sql.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(";")
    return s


def sql_match(pred: str, gold: str) -> bool:
    return normalize_sql(pred) == normalize_sql(gold)


@dataclass
class JudgeMetrics:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0


@dataclass
class PipelineMetrics:
    total: int = 0
    approved: int = 0
    total_iterations: int = 0
    execution_matches: int = 0
    risk_deltas: list[float] = field(default_factory=list)

    @property
    def approval_rate(self) -> float:
        return self.approved / self.total if self.total else 0.0

    @property
    def mean_iterations(self) -> float:
        return self.total_iterations / self.total if self.total else 0.0

    @property
    def execution_accuracy(self) -> float:
        return self.execution_matches / self.total if self.total else 0.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def compare_vuln_classes(predicted: set[str], expected: set[str], m: JudgeMetrics) -> None:
    m.true_positives += len(predicted & expected)
    m.false_positives += len(predicted - expected)
    m.false_negatives += len(expected - predicted)


def update_class_metrics(
    predicted: set[str], expected: set[str], by_class: dict[str, JudgeMetrics]
) -> None:
    for cls in predicted | expected:
        if cls not in by_class:
            by_class[cls] = JudgeMetrics()
        m = by_class[cls]
        if cls in predicted and cls in expected:
            m.true_positives += 1
        elif cls in predicted:
            m.false_positives += 1
        else:
            m.false_negatives += 1
