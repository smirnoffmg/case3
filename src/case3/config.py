"""Application settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Used when calling a local OpenAI-compatible server (Ollama) that ignores the key.
OLLAMA_PLACEHOLDER_API_KEY = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    schema_ddl_path: Path = ROOT / "data/schema/data_model.sql"
    schema_json_path: Path = ROOT / "data/derived/schema.json"
    sensitivity_path: Path = ROOT / "data/sensitivity.yaml"
    few_shot_path: Path = ROOT / "data/examples/few_shot.yaml"
    dataset_tasks_path: Path = ROOT / "data/dataset/tasks.jsonl"
    dataset_vulns_path: Path = ROOT / "data/dataset/vulns.jsonl"
    reports_dir: Path = ROOT / "reports"
    timeout_sec: float = 60.0
    max_iterations: int = 5
    use_llm: bool = True
    retriever_top_k: int = 8

    def resolve_llm_credentials(self) -> tuple[str, str | None]:
        """API key and base URL for LangChain (Ollama needs no real key)."""
        if self.openai_api_key:
            return self.openai_api_key, self.openai_base_url
        if self.openai_base_url:
            return OLLAMA_PLACEHOLDER_API_KEY, self.openai_base_url
        return OLLAMA_PLACEHOLDER_API_KEY, DEFAULT_OLLAMA_BASE_URL

    def llm_endpoint_label(self) -> str:
        _, base = self.resolve_llm_credentials()
        if base:
            return f"{self.openai_model} @ {base}"
        return self.openai_model


def get_settings() -> Settings:
    return Settings()
