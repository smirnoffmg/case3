"""LLM client (OpenAI-compatible API via LangChain)."""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from case3.config import Settings, get_settings
from case3.logging_config import log_llm_exchange

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Return model text for the prompt."""


class LangChainLLMClient:
    """OpenAI-compatible chat API via langchain-openai."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._api_key, self._base_url = self._settings.resolve_llm_credentials()

    def complete(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        if self._base_url:
            llm = ChatOpenAI(
                api_key=SecretStr(self._api_key),
                base_url=self._base_url,
                model=self._settings.openai_model,
                temperature=0.0,
            )
        else:
            llm = ChatOpenAI(
                api_key=SecretStr(self._api_key),
                model=self._settings.openai_model,
                temperature=0.0,
            )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        text = content if isinstance(content, str) else str(content)
        log_llm_exchange(logger, prompt, text)
        return text


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    return LangChainLLMClient(settings)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]
