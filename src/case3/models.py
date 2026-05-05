from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VulnerabilityClass(StrEnum):
    sql_injection = "sql_injection"
    union_based_injection = "union_based_injection"
    update_delete_without_where = "update_delete_without_where"
    plpgsql_unsafe_execute = "plpgsql_unsafe_execute"
    time_based_blind_injection = "time_based_blind_injection"
    privilege_escalation_security_definer = "privilege_escalation_security_definer"
    direct_access_sensitive_fields = "direct_access_sensitive_fields"
    select_star = "select_star"
    missing_limit = "missing_limit"


class SqlCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = Field(min_length=1)
    rationale: str = ""
    iteration: int = Field(ge=0)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vulnerability_class: VulnerabilityClass
    risk: int = Field(ge=0, le=10)
    explanation: str = Field(min_length=1)
    location: str | None = None
    suggested_fix: str | None = None
    source: Literal["static", "llm"]


class CritiqueLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_to_avoid: str = Field(min_length=1)
    correct_approach: str = Field(min_length=1)
    severity: int = Field(ge=0, le=10)
    seen_count: int = Field(ge=1)


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    ts: datetime
    type: Literal["generated", "judged", "lesson_added", "approved", "exhausted"]
    payload: dict[str, object]
