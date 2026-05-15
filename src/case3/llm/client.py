"""LLM client strategy: stub for tests, LangChain for production."""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from case3.config import Settings, get_settings


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Return model text for the prompt."""


class StubLLMClient:
    """Deterministic client: extracts task table hint and returns safe SELECT."""

    def complete(self, prompt: str) -> str:
        table = _extract_table_from_prompt(prompt)
        if "REPAIR" in prompt.upper() or "ИСПРАВ" in prompt.upper():
            return f"```sql\nSELECT id, name FROM public.{table} WHERE status = 1 LIMIT 10;\n```"
        return f"```sql\nSELECT id, name FROM public.{table} WHERE status = 1 LIMIT 10;\n```"


def _extract_table_from_prompt(prompt: str) -> str:
    m = re.search(r"public\.(\w+)", prompt)
    if m:
        return m.group(1)
    m = re.search(r"Table:\s*(\w+)", prompt, re.I)
    if m:
        return m.group(1)
    low = prompt.lower()
    if any(w in low for w in ("сотрудник", "employee", "email", "почт")):
        return "sys_employee"
    if any(w in low for w in ("счет", "счёт", "acc_number", "account")):
        return "acc_number"
    if any(w in low for w in ("организ", "org")):
        return "org"
    for name in ("sys_employee", "acc_number", "org"):
        if name in low:
            return name
    return "sys_employee"


class LangChainLLMClient:
    """OpenAI via langchain-openai."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            msg = "OPENAI_API_KEY is required for LangChainLLMClient"
            raise ValueError(msg)

    def complete(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        api_key = self._settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LangChainLLMClient")
        llm = ChatOpenAI(
            api_key=SecretStr(api_key),
            model=self._settings.openai_model,
            temperature=0.0,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, str):
            return content
        return str(content)


def get_llm_client(settings: Settings | None = None, force_stub: bool = False) -> LLMClient:
    settings = settings or get_settings()
    if force_stub or not settings.openai_api_key:
        return StubLLMClient()
    return LangChainLLMClient(settings)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]
