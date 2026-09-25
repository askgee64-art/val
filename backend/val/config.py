"""VAL configuration — externalized, no secrets in source."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


# Resolve project root: backend/val/config.py → backend → val/
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime settings for VAL MVP."""

    app_name: str = "VAL"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="VAL_ENV")
    debug: bool = Field(default=True, alias="VAL_DEBUG")

    # API
    api_host: str = Field(default="0.0.0.0", alias="VAL_API_HOST")
    api_port: int = Field(default=8000, alias="VAL_API_PORT")
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # Auth (MVP single-user founder)
    founder_token: str = Field(default="val-founder-dev-token", alias="VAL_FOUNDER_TOKEN")
    founder_user_id: str = Field(
        default="00000000-0000-4000-8000-000000000001", alias="VAL_FOUNDER_USER_ID"
    )
    founder_org_id: str = Field(
        default="00000000-0000-4000-8000-000000000010", alias="VAL_FOUNDER_ORG_ID"
    )
    founder_email: str = Field(default="founder@val.local", alias="VAL_FOUNDER_EMAIL")
    founder_display_name: str = Field(default="Tomiwa", alias="VAL_FOUNDER_NAME")

    # Database
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'val.db'}",
        alias="VAL_DATABASE_URL",
    )

    # Paths
    project_root: Path = _PROJECT_ROOT
    data_dir: Path = Field(default=_PROJECT_ROOT / "data")
    workspace_dir: Path = Field(default=_PROJECT_ROOT / "data" / "workspace")
    sandbox_dir: Path = Field(default=_PROJECT_ROOT / "data" / "sandbox")
    memory_dir: Path = Field(default=_PROJECT_ROOT / "data" / "memory")
    audit_dir: Path = Field(default=_PROJECT_ROOT / "data" / "audit")
    protected_dirs: list[str] = Field(
        default_factory=lambda: [
            str(_PROJECT_ROOT / "backend" / "val"),
            str(_PROJECT_ROOT / "data" / "audit"),
            str(_PROJECT_ROOT / ".git"),
            str(_PROJECT_ROOT / "backend" / "val" / "security"),
            str(_PROJECT_ROOT / "backend" / "val" / "permissions"),
        ]
    )

    # Model providers
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_default_model: str = Field(
        default="gemini-1.5-flash", alias="GEMINI_DEFAULT_MODEL"
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_default_model: str = Field(
        default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_DEFAULT_MODEL"
    )
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    default_model: str = Field(default="gemini-1.5-flash", alias="VAL_DEFAULT_MODEL")
    # When no API key: use deterministic local planner (still real planning logic)
    allow_local_fallback: bool = Field(default=True, alias="VAL_ALLOW_LOCAL_FALLBACK")

    # Hardware & Quantization
    preferred_quantization: str = Field(default="INT4", alias="VAL_PREFERRED_QUANTIZATION")
    auto_offload_heavy_to_cloud: bool = Field(default=True, alias="VAL_AUTO_OFFLOAD_HEAVY_TO_CLOUD")

    # Autonomy / safety
    max_plan_steps: int = 20
    max_tool_calls_per_task: int = 30
    max_recursion_depth: int = 5
    task_default_timeout_seconds: int = 300
    code_sandbox_timeout_seconds: int = 10
    code_sandbox_max_output_bytes: int = 100_000
    global_paused: bool = False

    # Memory
    working_memory_ttl_hours: int = 24
    short_term_memory_ttl_days: int = 14
    max_working_memory_items: int = 50

    model_config = ConfigDict(env_file=".env", extra="ignore")

    def ensure_directories(self) -> None:
        for d in (
            self.data_dir,
            self.workspace_dir,
            self.sandbox_dir,
            self.memory_dir,
            self.audit_dir,
        ):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
