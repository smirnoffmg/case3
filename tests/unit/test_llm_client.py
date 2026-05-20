from unittest.mock import MagicMock

import pytest

from case3.config import Settings
from case3.llm.client import (
    LangChainAnthropicClient,
    LangChainOpenAIClient,
    get_llm_client,
)


def _settings(**kwargs: object) -> Settings:
    return Settings.model_construct(**kwargs)  # type: ignore[arg-type]


def test_get_llm_client_openai_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(llm_provider="openai", openai_api_key="sk-test")
    client = get_llm_client(settings)
    assert isinstance(client, LangChainOpenAIClient)


def test_get_llm_client_anthropic_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key="sk-ant-test")
    client = get_llm_client(settings)
    assert isinstance(client, LangChainAnthropicClient)


def test_openai_complete_invokes_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_response = MagicMock()
    mock_response.content = "SELECT 1"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    mock_chat_openai = MagicMock(return_value=mock_llm)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", mock_chat_openai)

    settings = _settings(llm_provider="openai", openai_api_key="sk-test")
    text = LangChainOpenAIClient(settings).complete("prompt")
    assert text == "SELECT 1"
    mock_llm.invoke.assert_called_once()


def test_anthropic_complete_invokes_chat_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_response = MagicMock()
    mock_response.content = "SELECT 2"
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response

    mock_chat_anthropic = MagicMock(return_value=mock_llm)
    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", mock_chat_anthropic)

    settings = _settings(llm_provider="anthropic", anthropic_api_key="sk-ant-test")
    text = LangChainAnthropicClient(settings).complete("prompt")
    assert text == "SELECT 2"
    mock_llm.invoke.assert_called_once()


def test_anthropic_client_requires_api_key() -> None:
    settings = _settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        LangChainAnthropicClient(settings)
