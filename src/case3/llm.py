from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from case3.config import Config


def get_chat_model(_config: Config) -> BaseChatModel:
    """
    Real LLM wiring is intentionally deferred.
    In unit tests, use FakeListChatModel from langchain-core directly.
    """
    raise NotImplementedError("Wire a real ChatModel in a later step (TDD: tests first).")
