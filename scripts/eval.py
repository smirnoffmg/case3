from __future__ import annotations

import json
from pathlib import Path

from case3.evaluator import Metrics, evaluate


def main() -> None:
    import typer

    app = typer.Typer(add_completion=False)

    @app.command()
    def run_eval(
        tasks: Path = Path("data/examples/tasks.jsonl"),
        ddl: Path = Path("data/ddl/synthetic.sql"),
    ) -> None:
        # Offline dummy evaluation for now.
        from langchain_core.language_models.fake import FakeListLLM

        from case3.generator.prompt_rag import PromptRagGenerator
        from case3.judge.base import Judge
        from case3.judge.llm import LlmJudge
        from case3.judge.static import StaticJudge

        class Invoker:
            def __init__(self, llm: FakeListLLM):
                self._llm = llm

            def invoke(self, prompt: str) -> str:
                return str(self._llm.invoke(prompt))

        gen = PromptRagGenerator(
            llm=Invoker(FakeListLLM(responses=['{"sql":"SELECT 1","rationale":"ok"}']))
        )
        judges: list[Judge] = [StaticJudge(), LlmJudge(llm=Invoker(FakeListLLM(responses=["[]"])))]

        m: Metrics = evaluate(tasks_path=tasks, ddl_path=ddl, generator=gen, judges=judges)
        print(json.dumps(m.__dict__, ensure_ascii=False, indent=2))

    app()


if __name__ == "__main__":
    main()
