from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ArtifactConfig:
    backend: str
    artifacts_dir: Path
    cache_dir: Path
    s3_endpoint: str | None
    s3_bucket: str | None
    s3_region: str | None
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_force_path_style: bool


@dataclass(frozen=True)
class BotExecutionConfig:
    mode: str
    container_host: str
    container_timeout_seconds: float
    container_cpu: float
    container_memory: str
    container_pids_limit: int
    container_network: str | None
    docker_bin: str
    container_port: int


def get_artifact_config(repo_root: Path | None = None) -> ArtifactConfig:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    artifacts_dir = Path(_env("BOT_ARTIFACTS_DIR", str(repo_root / "runtime" / "artifacts")))
    cache_dir = Path(_env("BOT_ARTIFACT_CACHE_DIR", str(artifacts_dir / "cache")))
    return ArtifactConfig(
        backend=_env("BOT_ARTIFACT_BACKEND", "filesystem"),
        artifacts_dir=artifacts_dir,
        cache_dir=cache_dir,
        s3_endpoint=_env("S3_ENDPOINT"),
        s3_bucket=_env("S3_BUCKET"),
        s3_region=_env("S3_REGION", "us-east-1"),
        s3_access_key=_env("S3_ACCESS_KEY"),
        s3_secret_key=_env("S3_SECRET_KEY"),
        s3_force_path_style=_bool_env("S3_FORCE_PATH_STYLE", default=True),
    )


def get_bot_execution_config() -> BotExecutionConfig:
    return BotExecutionConfig(
        mode=_env("BOT_EXECUTION_MODE", "local"),
        container_host=_env("BOT_CONTAINER_HOST", "127.0.0.1"),
        container_timeout_seconds=_float_env("BOT_CONTAINER_TIMEOUT", 2.0),
        container_cpu=_float_env("BOT_CONTAINER_CPU", 0.5),
        container_memory=_env("BOT_CONTAINER_MEM", "256m"),
        container_pids_limit=_int_env("BOT_CONTAINER_PIDS_LIMIT", 128),
        container_network=_env("BOT_CONTAINER_NETWORK"),
        docker_bin=_env("BOT_DOCKER_BIN", "docker"),
        container_port=_int_env("BOT_CONTAINER_PORT", 8080),
    )
