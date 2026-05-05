from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from case3.models import AuditEvent


def write_event(path: Path, event: AuditEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = event.model_dump_json() + "\n"
    if path.exists():
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    else:
        path.write_text(line, encoding="utf-8")


def read_events(path: Path) -> list[AuditEvent]:
    if not path.exists():
        return []
    events: list[AuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(AuditEvent.model_validate_json(line))
    return events


def render_report(events: Iterable[AuditEvent]) -> str:
    """
    KISS text report from an event stream.
    """
    lines: list[str] = []
    for e in events:
        ts = e.ts.isoformat(timespec="seconds")
        lines.append(f"[{ts}] {e.type} {json.dumps(e.payload, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines).strip() + ("\n" if lines else "")


def new_event(
    *,
    run_id: UUID,
    type: Literal["generated", "judged", "lesson_added", "approved", "exhausted"],
    payload: dict[str, object],
) -> AuditEvent:
    return AuditEvent(run_id=run_id, ts=datetime.now(UTC), type=type, payload=payload)
