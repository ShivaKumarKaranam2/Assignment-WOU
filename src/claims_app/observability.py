from __future__ import annotations

import os

from claims_app.config import settings


def configure_observability() -> None:
    if settings.langchain_tracing_v2:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    if settings.langchain_project:
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)


def langsmith_status() -> dict[str, bool | str]:
    return {
        "tracing_enabled": bool(settings.langchain_tracing_v2),
        "project_name": settings.langchain_project,
        "api_key_configured": bool(settings.langsmith_api_key),
        "ready": bool(settings.langchain_tracing_v2 and settings.langsmith_api_key),
    }
