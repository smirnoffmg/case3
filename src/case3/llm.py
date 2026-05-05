from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from case3.config import Config


def get_chat_model(config: Config) -> BaseChatModel:
    if config.llm_provider != "openai":
        raise ValueError(f"Unsupported llm_provider: {config.llm_provider!r}")
    api_key = SecretStr(config.openai_api_key) if config.openai_api_key else None
    return ChatOpenAI(model=config.openai_model, api_key=api_key)


@dataclass(frozen=True)
class LangChainChatInvoker:
    model: BaseChatModel

    def invoke(self, prompt: str) -> str:
        msg: BaseMessage = self.model.invoke(prompt)
        return str(getattr(msg, "content", msg))
