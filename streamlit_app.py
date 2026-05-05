from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import yaml
from langchain_core.language_models.fake import FakeListLLM

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


def _load_sensitivity(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): bool(v) for k, v in data.items()}


def _load_schema(*, ddl_path: Path, sensitivity_path: Path) -> list[TableInfo]:
    ddl = ddl_path.read_text(encoding="utf-8")
    sensitivity = _load_sensitivity(sensitivity_path)
    return parse_ddl(ddl, sensitivity=sensitivity)


@dataclass
class _LangChainInvoker:
    llm: FakeListLLM

    def invoke(self, prompt: str) -> str:
        return str(self.llm.invoke(prompt))


st.set_page_config(page_title="case3 demo", layout="wide")
st.title("SQL Generation & Security Audit (MVP)")

ddl_path = Path(st.text_input("DDL path", value="data/ddl/synthetic.sql"))
sensitivity_path = Path(st.text_input("Sensitivity YAML path", value="data/sensitivity.yaml"))
task = st.text_area("NL task", value="Get first user id", height=100)

use_fake_llm = st.checkbox("Use fake LLM (offline)", value=True)

if st.button("Run"):
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

    result = run(
        task,
        generator=generator,
        judges=judges,
        memory=memory,
        retriever=retriever,
        full_schema=full_schema,
        config=cfg,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Result")
        st.code(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))

    with col2:
        st.subheader("Iterations")
        for i, findings in enumerate(result.findings_per_iter):
            st.markdown(f"**Iteration {i}**")
            if not findings:
                st.write("(no findings)")
            else:
                for f in findings:
                    st.write(
                        {
                            "class": f.vulnerability_class.value,
                            "risk": f.risk,
                            "source": f.source,
                            "suggested_fix": f.suggested_fix,
                        }
                    )
