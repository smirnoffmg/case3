"""Typer CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from case3.config import get_settings
from case3.eval.runner import run_eval
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import save_schema_index
from case3.schema_index.parser import build_schema_index

app = typer.Typer(help="SQL generation + security audit (Case 3)")


@app.command("build-schema")
def build_schema(
    ddl: Path | None = typer.Option(None, help="Path to data_model.sql"),
    out: Path | None = typer.Option(None, help="Output schema.json path"),
) -> None:
    settings = get_settings()
    ddl_path = ddl or settings.schema_ddl_path
    out_path = out or settings.schema_json_path
    index = build_schema_index(ddl_path)
    save_schema_index(index, out_path)
    typer.echo(f"Wrote {len(index.tables)} tables -> {out_path}")


@app.command("run")
def run_task(
    task: str = typer.Argument(..., help="Natural language task"),
    max_iterations: int | None = typer.Option(None, "--max-iterations", "-n"),
    stub: bool = typer.Option(False, "--stub", help="Force stub LLM"),
) -> None:
    result = run_sql_security_pipeline(
        task,
        max_iterations=max_iterations,
        generator_kwargs={"force_stub": stub},
        auditor_kwargs={"force_stub": stub, "use_llm": not stub},
    )
    typer.echo(result.final_sql)
    typer.echo(f"\nApproved: {result.approved} | Iterations: {result.iterations_used}")
    if not result.approved:
        sys.exit(1)


@app.command("eval")
def eval_cmd(limit: int | None = typer.Option(None, help="Max tasks to run")) -> None:
    report = run_eval(limit=limit)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
