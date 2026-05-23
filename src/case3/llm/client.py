"""LLM clients for Ollama, OpenAI, and Anthropic (Claude)."""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from case3.config import (
    LLMProvider,
    Settings,
    get_settings,
)
from case3.logging_config import log_llm_exchange

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Return model text for the prompt."""


class LangChainOpenAIClient:
    """OpenAI-compatible chat API via langchain-openai (Ollama, OpenAI, proxies)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._api_key, self._base_url = self._settings.resolve_llm_credentials()

    def complete(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        temp = self._settings.llm_temperature
        if self._base_url:
            llm = ChatOpenAI(
                api_key=SecretStr(self._api_key),
                base_url=self._base_url,
                model=self._settings.openai_model,
                temperature=temp,
                extra_body={"num_ctx": self._settings.llm_num_ctx},
            )
        else:
            llm = ChatOpenAI(
                api_key=SecretStr(self._api_key),
                model=self._settings.openai_model,
                temperature=temp,
            )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        text = content if isinstance(content, str) else str(content)
        um = response.usage_metadata
        log_llm_exchange(
            logger,
            prompt,
            text,
            input_tokens=um["input_tokens"] if um else None,
            output_tokens=um["output_tokens"] if um else None,
        )
        return text


class LangChainAnthropicClient:
    """Anthropic Claude via langchain-anthropic."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.anthropic_api_key:
            msg = "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            raise ValueError(msg)

    def complete(self, prompt: str) -> str:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage
        from pydantic import SecretStr

        llm = ChatAnthropic(  # type: ignore[call-arg]
            api_key=SecretStr(self._settings.anthropic_api_key or ""),
            model_name=self._settings.anthropic_model,
            temperature=self._settings.llm_temperature,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        text = content if isinstance(content, str) else str(content)
        um = response.usage_metadata
        log_llm_exchange(
            logger,
            prompt,
            text,
            input_tokens=um["input_tokens"] if um else None,
            output_tokens=um["output_tokens"] if um else None,
        )
        return text


# Backward-compatible alias
LangChainLLMClient = LangChainOpenAIClient


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    provider = settings.resolve_llm_provider()
    if provider == LLMProvider.ANTHROPIC:
        return LangChainAnthropicClient(settings)
    return LangChainOpenAIClient(settings)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]
