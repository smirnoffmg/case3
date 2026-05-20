"""Application settings."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Used when calling a local OpenAI-compatible server (Ollama) that ignores the key.
OLLAMA_PLACEHOLDER_API_KEY = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_OPENAI_PLACEHOLDER_KEYS = frozenset({OLLAMA_PLACEHOLDER_API_KEY, "local", ""})

LLMProviderName = Literal["ollama", "openai", "anthropic"]


class LLMProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AmbiguousLLMConfigError(ValueError):
    """Raised when both cloud API keys are set without explicit LLM_PROVIDER."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: LLMProviderName | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    schema_ddl_path: Path = ROOT / "data/schema/data_model.sql"
    schema_json_path: Path = ROOT / "data/derived/schema.json"
    sensitivity_path: Path = ROOT / "data/sensitivity.yaml"
    few_shot_path: Path = ROOT / "data/examples/few_shot.yaml"
    dataset_tasks_path: Path = ROOT / "data/dataset/tasks.jsonl"
    dataset_vulns_path: Path = ROOT / "data/dataset/vulns.jsonl"
    reports_dir: Path = ROOT / "reports"
    timeout_sec: float = 60.0
    max_iterations: int = 5
    retriever_top_k: int = 8
    llm_temperature: float = 0.0
    risk_threshold: float = 4.0
    hard_block_risk: float = 8.0
    eval_database_url: str | None = None
    streamlit_page_title: str = "SQL Security System"
    streamlit_layout: str = "wide"

    def _is_openai_cloud_key(self) -> bool:
        key = (self.openai_api_key or "").strip()
        return bool(key) and key not in _OPENAI_PLACEHOLDER_KEYS

    def _has_ambiguous_cloud_keys(self) -> bool:
        return self._is_openai_cloud_key() and bool(self.anthropic_api_key)

    def resolve_llm_provider(self) -> LLMProvider:
        if self.llm_provider is not None:
            return LLMProvider(self.llm_provider)

        if self._has_ambiguous_cloud_keys():
            raise AmbiguousLLMConfigError(
                "Both OPENAI_API_KEY and ANTHROPIC_API_KEY are set. "
                "Set LLM_PROVIDER to 'openai' or 'anthropic' explicitly."
            )

        # An explicit OPENAI_BASE_URL is a deliberate endpoint choice (local
        # Ollama, OpenAI-compat proxy). Honor it even when ANTHROPIC_API_KEY
        # leaks in from the shell environment.
        if self.openai_base_url:
            return LLMProvider.OLLAMA
        if self.anthropic_api_key:
            return LLMProvider.ANTHROPIC
        if self._is_openai_cloud_key():
            return LLMProvider.OPENAI
        return LLMProvider.OLLAMA

    def resolve_llm_credentials(self) -> tuple[str, str | None]:
        """API key and base URL for OpenAI-compatible LangChain client (Ollama path)."""
        if self.openai_api_key:
            return self.openai_api_key, self.openai_base_url
        if self.openai_base_url:
            return OLLAMA_PLACEHOLDER_API_KEY, self.openai_base_url
        return OLLAMA_PLACEHOLDER_API_KEY, DEFAULT_OLLAMA_BASE_URL

    def llm_endpoint_label(self) -> str:
        provider = self.resolve_llm_provider()
        if provider == LLMProvider.ANTHROPIC:
            return f"{self.anthropic_model} @ anthropic"
        _, base = self.resolve_llm_credentials()
        model = self.openai_model
        if provider == LLMProvider.OPENAI and not base:
            return f"{model} @ openai"
        if base:
            return f"{model} @ {base}"
        return model


def get_settings() -> Settings:
    return Settings()
