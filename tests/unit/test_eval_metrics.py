from __future__ import annotations

from case3.evaluator import aggregate_metrics, max_risk_per_iter, repeated_classes_between_iters
from case3.models import CritiqueLesson, Finding, OrchestratorState, RunResult, VulnerabilityClass


def test_eval_max_risk_and_repeated_classes() -> None:
    r = RunResult(
        final_state=OrchestratorState.approved,
        iterations=2,
        final_sql="SELECT 1",
        findings_per_iter=[
            [
                Finding(
                    vulnerability_class=VulnerabilityClass.select_star,
                    risk=5,
                    explanation="x",
                    location=None,
                    suggested_fix=None,
                    source="static",
                )
            ],
            [
                Finding(
                    vulnerability_class=VulnerabilityClass.select_star,
                    risk=4,
                    explanation="x",
                    location=None,
                    suggested_fix=None,
                    source="static",
                ),
                Finding(
                    vulnerability_class=VulnerabilityClass.missing_limit,
                    risk=4,
                    explanation="x",
                    location=None,
                    suggested_fix=None,
                    source="static",
                ),
            ],
        ],
        lessons_per_iter=[
            [CritiqueLesson(pattern_to_avoid="a", correct_approach="b", severity=5, seen_count=1)]
        ],
    )

    assert max_risk_per_iter(r) == [5, 4]
    assert repeated_classes_between_iters(r) == 1  # select_star repeats


def test_aggregate_metrics_empty() -> None:
    m = aggregate_metrics([])
    assert m.avg_iterations == 0.0
    assert m.avg_max_risk == 0.0
    assert m.repeated_classes_rate == 0.0
