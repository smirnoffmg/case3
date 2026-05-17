from case3.config import (
    DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_PLACEHOLDER_API_KEY,
    Settings,
)


def test_ollama_fallback_without_key():
    s = Settings(openai_api_key=None, openai_base_url=None, openai_model="qwen2.5:7b")
    key, base = s.resolve_llm_credentials()
    assert key == OLLAMA_PLACEHOLDER_API_KEY
    assert base == DEFAULT_OLLAMA_BASE_URL


def test_ollama_with_base_url_only():
    s = Settings(
        openai_api_key=None,
        openai_base_url="http://localhost:11434/v1",
        openai_model="qwen2.5:7b",
    )
    key, base = s.resolve_llm_credentials()
    assert key == OLLAMA_PLACEHOLDER_API_KEY
    assert base == "http://localhost:11434/v1"


def test_cloud_keeps_key():
    s = Settings(openai_api_key="sk-test", openai_base_url=None)
    key, base = s.resolve_llm_credentials()
    assert key == "sk-test"
    assert base is None
