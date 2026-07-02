from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nvidia_llm_api_key: str = Field(default="", alias="NVIDIA_LLM_MODEL")
    nvidia_ocr_api_key: str = Field(default="", alias="NVIDIA_OCR_MODEL")
    nvidia_chat_model: str = Field(default="minimaxai/minimax-m3", alias="NVIDIA_CHAT_MODEL")
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field(default="claims-agentic-health", alias="LANGCHAIN_PROJECT")
    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    policy_file: Path = Field(default=Path("data/policy_terms.json"), alias="POLICY_FILE")
    max_upload_bytes: int = Field(default=10_000_000, alias="MAX_UPLOAD_BYTES")
    temperature: float = Field(default=0.2, alias="NVIDIA_TEMPERATURE")
    top_p: float = Field(default=0.95, alias="NVIDIA_TOP_P")
    max_tokens: int = Field(default=4096, alias="NVIDIA_MAX_TOKENS")


settings = Settings()
