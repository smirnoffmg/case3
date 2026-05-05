from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CASE3_",
        env_file=".env",
        extra="ignore",
    )

    # Orchestrator
    max_iters: int = 4
    approve_risk_threshold: int = 4
    hard_block_risk_threshold: int = 7

    # LLM (only used when building real Generator/Judge)
    llm_provider: str = "openai"
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
