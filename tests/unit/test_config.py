import pytest

from case3.config import (
    DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_PLACEHOLDER_API_KEY,
    AmbiguousLLMConfigError,
    LLMProvider,
    Settings,
)


def _settings(**kwargs: object) -> Settings:
    """Build settings without reading `.env` or process environment."""
    return Settings.model_construct(**kwargs)  # type: ignore[arg-type]


def test_ollama_fallback_without_key():
    s = _settings(openai_api_key=None, openai_base_url=None, openai_model="qwen2.5:7b")
    key, base = s.resolve_llm_credentials()
    assert key == OLLAMA_PLACEHOLDER_API_KEY
    assert base == DEFAULT_OLLAMA_BASE_URL
    assert s.resolve_llm_provider() == LLMProvider.OLLAMA


def test_ollama_with_base_url_only():
    s = _settings(
        openai_api_key=None,
        openai_base_url="http://localhost:11434/v1",
        openai_model="qwen2.5:7b",
    )
    key, base = s.resolve_llm_credentials()
    assert key == OLLAMA_PLACEHOLDER_API_KEY
    assert base == "http://localhost:11434/v1"
    assert s.resolve_llm_provider() == LLMProvider.OLLAMA


def test_cloud_keeps_key():
    s = _settings(openai_api_key="sk-test", openai_base_url=None)
    key, base = s.resolve_llm_credentials()
    assert key == "sk-test"
    assert base is None
    assert s.resolve_llm_provider() == LLMProvider.OPENAI


def test_anthropic_auto_detect():
    s = _settings(anthropic_api_key="sk-ant-test", anthropic_model="claude-sonnet-4-20250514")
    assert s.resolve_llm_provider() == LLMProvider.ANTHROPIC
    assert s.llm_endpoint_label() == "claude-sonnet-4-20250514 @ anthropic"


def test_explicit_llm_provider_overrides_auto():
    s = _settings(
        llm_provider="openai",
        openai_api_key="sk-test",
        anthropic_api_key="sk-ant-test",
    )
    assert s.resolve_llm_provider() == LLMProvider.OPENAI


def test_ambiguous_dual_key_raises():
    s = _settings(openai_api_key="sk-test", anthropic_api_key="sk-ant-test")
    with pytest.raises(AmbiguousLLMConfigError):
        s.resolve_llm_provider()


def test_placeholder_openai_key_with_anthropic_not_ambiguous():
    s = _settings(
        openai_api_key="local",
        openai_base_url="http://localhost:11434/v1",
        anthropic_api_key="sk-ant-test",
    )
    assert s.resolve_llm_provider() == LLMProvider.ANTHROPIC


def test_ollama_explicit_over_anthropic_key():
    s = _settings(
        llm_provider="ollama",
        openai_base_url="http://localhost:11434/v1",
        anthropic_api_key="sk-ant-test",
    )
    assert s.resolve_llm_provider() == LLMProvider.OLLAMA


def test_openai_endpoint_label():
    s = _settings(openai_api_key="sk-test", openai_model="gpt-4o-mini")
    assert s.llm_endpoint_label() == "gpt-4o-mini @ openai"


def test_ollama_endpoint_label_with_base():
    s = _settings(
        openai_base_url="http://localhost:11434/v1",
        openai_model="qwen2.5:7b",
    )
    assert s.llm_endpoint_label() == "qwen2.5:7b @ http://localhost:11434/v1"


def test_risk_defaults():
    s = Settings()
    assert s.risk_threshold == 4.0
    assert s.hard_block_risk == 8.0
    assert s.llm_temperature == 0.0


def test_model_copy_preserves_env_key_when_ui_empty():
    s = Settings(openai_api_key="sk-env", openai_model="m1")
    copy = s.model_copy(update={"openai_model": "m2"})
    assert copy.openai_api_key == "sk-env"
    assert copy.openai_model == "m2"
