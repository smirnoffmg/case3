from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from case3.audit import read_events, render_report, write_event
from case3.models import AuditEvent


def test_audit_write_and_read_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    run_id = UUID("00000000-0000-0000-0000-000000000001")

    e1 = AuditEvent(
        run_id=run_id,
        ts=datetime(2020, 1, 1, tzinfo=UTC),
        type="generated",
        payload={"iteration": 0},
    )
    e2 = AuditEvent(
        run_id=run_id,
        ts=datetime(2020, 1, 1, 0, 0, 1, tzinfo=UTC),
        type="approved",
        payload={"sql": "SELECT 1"},
    )

    write_event(path, e1)
    write_event(path, e2)

    events = read_events(path)
    assert events == [e1, e2]


def test_render_report_is_stable_and_newline_terminated() -> None:
    run_id = UUID("00000000-0000-0000-0000-000000000001")
    e = AuditEvent(
        run_id=run_id,
        ts=datetime(2020, 1, 1, tzinfo=UTC),
        type="generated",
        payload={"b": 2, "a": 1},
    )

    report = render_report([e])
    assert report.endswith("\n")
    assert '"a": 1' in report
    assert '"b": 2' in report
