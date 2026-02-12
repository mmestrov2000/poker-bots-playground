from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    name: str
    admin_user: str
    admin_password: str
    shared_schema: str
    private_schema_prefix: str
    sslmode: str
    enabled: bool

    @property
    def admin_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.admin_user}:{self.admin_password}"
            f"@{self.host}:{self.port}/{self.name}?sslmode={self.sslmode}"
        )

    def bot_dsn(self, username: str, password: str) -> str:
        return (
            f"postgresql+psycopg://{username}:{password}"
            f"@{self.host}:{self.port}/{self.name}?sslmode={self.sslmode}"
        )


def get_db_config() -> DBConfig:
    explicit_enabled = _bool_env("DB_ENABLED")
    enabled = explicit_enabled if explicit_enabled is not None else os.getenv("DB_HOST") is not None
    return DBConfig(
        host=_env("DB_HOST", "localhost"),
        port=int(_env("DB_PORT", "5432")),
        name=_env("DB_NAME", "poker_bots"),
        admin_user=_env("DB_ADMIN_USER", "postgres"),
        admin_password=_env("DB_ADMIN_PASSWORD", "postgres"),
        shared_schema=_env("DB_SHARED_SCHEMA", "shared"),
        private_schema_prefix=_env("DB_PRIVATE_SCHEMA_PREFIX", "bot_"),
        sslmode=_env("DB_SSLMODE", "disable"),
        enabled=enabled,
    )


def is_db_enabled() -> bool:
    return get_db_config().enabled
