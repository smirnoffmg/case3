"""Application settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
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


def get_settings() -> Settings:
    return Settings()
