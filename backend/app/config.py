"""Environment-driven configuration for the Project SRT backend.

Rule 16 (Environment Configuration): configuration is separated by ENVIRONMENT
(development / testing / production) and driven entirely by environment
variables (loaded from a local, untracked .env file in development). No
secrets are hardcoded here or anywhere else in the repository — see
.env.example for the documented placeholder keys and .gitignore for what is
excluded from version control.

This module intentionally holds only the handful of settings needed to prove
the environment works in Phase 2 (environment name, API host/port, log
level). Business configuration (database URL, object storage, JWT signing
keys, etc.) is added by the phase that introduces the corresponding feature,
not invented speculatively here.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"  # development | testing | production
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"


settings = Settings()
