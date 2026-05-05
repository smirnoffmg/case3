from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import typer
import yaml
from langchain_core.language_models.fake import FakeListLLM

from case3.audit import new_event, read_events, render_report, write_event
from case3.config import Config
from case3.generator.prompt_rag import LlmInvoker as GeneratorInvoker
from case3.generator.prompt_rag import PromptRagGenerator
from case3.judge.base import Judge
from case3.judge.llm import LlmJudge
from case3.judge.static import StaticJudge
from case3.llm import LangChainChatInvoker, get_chat_model
from case3.memory import CritiqueMemory
from case3.models import TableInfo
from case3.orchestrator import run
from case3.schema_index.parser import parse_ddl
from case3.schema_index.retriever import Bm25SchemaRetriever

app = typer.Typer(add_completion=False)
schema_app = typer.Typer(add_completion=False)
audit_app = typer.Typer(add_completion=False)

app.add_typer(schema_app, name="schema")
app.add_typer(audit_app, name="audit")


def _load_sensitivity(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    out: dict[str, bool] = {}
    for k, v in data.items():
        out[str(k).lower()] = bool(v)
    return out


def _load_schema(*, ddl_path: Path, sensitivity_path: Path) -> list[TableInfo]:
    ddl = ddl_path.read_text(encoding="utf-8")
    sensitivity = _load_sensitivity(sensitivity_path)
    return parse_ddl(ddl, sensitivity=sensitivity)


@dataclass
class _LangChainInvoker:
    llm: FakeListLLM

    def invoke(self, prompt: str) -> str:
        return str(self.llm.invoke(prompt))


@app.command()
def run_task(
    task: str = typer.Argument(..., help="Natural language task description"),
    ddl_path: Path = typer.Option(
        Path("data/ddl/synthetic.sql"), "--ddl", exists=True, readable=True
    ),
    sensitivity_path: Path = typer.Option(
        Path("data/sensitivity.yaml"), "--sensitivity", exists=False, readable=True
    ),
    audit_path: Path = typer.Option(Path("out/audit.jsonl"), "--audit"),
    use_fake_llm: bool = typer.Option(
        True, "--use-fake-llm/--no-use-fake-llm", help="Use deterministic fake LLM output"
    ),
) -> None:
    """
    Run NL→SQL generation + audit loop (offline by default).
    """
    cfg = Config()
    full_schema = _load_schema(ddl_path=ddl_path, sensitivity_path=sensitivity_path)
    retriever = Bm25SchemaRetriever(full_schema)

    if use_fake_llm:
        gen_llm: GeneratorInvoker = _LangChainInvoker(
            FakeListLLM(responses=['{"sql":"SELECT id FROM users LIMIT 1","rationale":"ok"}'])
        )
        judge_llm: GeneratorInvoker = _LangChainInvoker(FakeListLLM(responses=["[]"]))
    else:
        chat = get_chat_model(cfg)
        gen_llm = LangChainChatInvoker(chat)
        judge_llm = LangChainChatInvoker(chat)

    generator = PromptRagGenerator(llm=gen_llm)
    judges: list[Judge] = [StaticJudge(), LlmJudge(llm=judge_llm)]
    memory = CritiqueMemory()

    run_id = uuid4()
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    result = run(
        task,
        generator=generator,
        judges=judges,
        memory=memory,
        retriever=retriever,
        full_schema=full_schema,
        config=cfg,
    )

    # Minimal audit events for MVP
    write_event(audit_path, new_event(run_id=run_id, type="generated", payload={"task": task}))
    write_event(
        audit_path,
        new_event(
            run_id=run_id,
            type="judged",
            payload={"iterations": result.iterations, "final_state": result.final_state},
        ),
    )
    write_event(
        audit_path,
        new_event(
            run_id=run_id,
            type="approved" if result.final_state == "approved" else "exhausted",
            payload={"final_sql": result.final_sql},
        ),
    )

    typer.echo(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


@schema_app.command("parse")
def schema_parse(
    ddl_path: Path = typer.Argument(..., exists=True, readable=True),
    sensitivity_path: Path = typer.Option(Path("data/sensitivity.yaml"), "--sensitivity"),
) -> None:
    tables = _load_schema(ddl_path=ddl_path, sensitivity_path=sensitivity_path)
    typer.echo(f"tables: {len(tables)}")
    for t in tables:
        typer.echo(f"- {t.name} ({len(t.columns)} cols, {len(t.foreign_keys)} fks)")


@audit_app.command("show")
def audit_show(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    events = read_events(path)
    typer.echo(render_report(events))
