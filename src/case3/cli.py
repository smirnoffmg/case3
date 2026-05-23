"""Typer CLI."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer

from case3.config import get_settings
from case3.eval.runner import run_eval
from case3.logging_config import begin_llm_exchange_log, configure_logging, verbosity
from case3.pipeline import run_sql_security_pipeline
from case3.schema_index.loader import save_schema_index
from case3.schema_index.parser import build_schema_index

app = typer.Typer(help="SQL generation + security audit (Case 3)")
logger = logging.getLogger(__name__)

VerboseOption = Annotated[
    int,
    typer.Option(
        "--verbose",
        "-v",
        count=True,
        help="Increase log detail (-v iterations, -vv SQL/vulns, -vvv LLM I/O)",
    ),
]


@app.command("build-schema")
def build_schema(
    ddl: Path | None = typer.Option(None, help="Path to data_model.sql"),
    out: Path | None = typer.Option(None, help="Output schema.json path"),
    verbose: VerboseOption = 0,
) -> None:
    configure_logging(verbose)
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
    verbose: VerboseOption = 0,
    log_file: Path | None = typer.Option(
        None, "--log-file", help="Write audit log markdown to this path"
    ),
) -> None:
    configure_logging(verbose)
    if verbose >= 1:
        logger.info("LLM: %s", get_settings().llm_endpoint_label())

    with begin_llm_exchange_log() as exchanges:
        result = run_sql_security_pipeline(task, max_iterations=max_iterations)

    total_in = sum(e.input_tokens or 0 for e in exchanges)
    total_out = sum(e.output_tokens or 0 for e in exchanges)
    token_info = f" | Tokens: {total_in}↑ {total_out}↓" if (total_in or total_out) else ""

    # Final SQL always on stdout
    typer.echo(result.final_sql)
    typer.echo(f"\nApproved: {result.approved} | Iterations: {result.iterations_used}{token_info}")

    if verbosity() >= 2:
        typer.echo("\n" + result.audit_log, err=True)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(result.audit_log, encoding="utf-8")
        logger.info("Audit log written to %s", log_file)

    if not result.approved:
        sys.exit(1)


@app.command("eval")
def eval_cmd(
    limit: int | None = typer.Option(None, help="Max tasks to run"),
    verbose: VerboseOption = 0,
) -> None:
    configure_logging(verbose)
    report = run_eval(limit=limit)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
