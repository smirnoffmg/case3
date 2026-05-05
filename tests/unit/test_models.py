from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import ValidationError

from case3.models import Finding, SqlCandidate, VulnerabilityClass


def test_sql_candidate_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SqlCandidate(
            **cast(
                Any,
                {
                    "sql": "select 1",
                    "iteration": 0,
                    "rationale": "",
                    "extra_field": "nope",
                },
            )
        )


def test_finding_validates_risk_range() -> None:
    with pytest.raises(ValidationError):
        Finding(
            vulnerability_class=VulnerabilityClass.sql_injection,
            risk=11,
            explanation="bad",
            source="static",
        )
