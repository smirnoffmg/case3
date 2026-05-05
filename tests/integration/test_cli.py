from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from case3.cli import app

runner = CliRunner()


def test_cli_schema_parse(tmp_path: Path) -> None:
    ddl = tmp_path / "schema.sql"
    ddl.write_text(
        "CREATE TABLE users (id BIGINT PRIMARY KEY, email TEXT NOT NULL);",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["schema", "parse", str(ddl)])
    assert result.exit_code == 0
    assert "tables: 1" in result.stdout


def test_cli_run_writes_audit_and_returns_json(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    ddl_path = Path("data/ddl/synthetic.sql")

    result = runner.invoke(
        app,
        [
            "run-task",
            "Get first user id",
            "--ddl",
            str(ddl_path),
            "--audit",
            str(audit),
            "--use-fake-llm",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["final_state"] in {"approved", "exhausted"}
    assert audit.exists()

    show = runner.invoke(app, ["audit", "show", str(audit)])
    assert show.exit_code == 0
    assert "approved" in show.stdout or "exhausted" in show.stdout
