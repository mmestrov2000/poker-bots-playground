from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from app.db.config import DBConfig, get_db_config


def maybe_bootstrap_shared_schema(
    *,
    repo_root: Path | None = None,
    config: DBConfig | None = None,
    logger: logging.Logger | None = None,
) -> None:
    config = config or get_db_config()
    if not config.enabled:
        return
    if not _bool_env("DB_BOOTSTRAP_ON_STARTUP", default=True):
        return
    repo_root = repo_root or Path(__file__).resolve().parents[3]
    logger = logger or logging.getLogger(__name__)
    retries = _int_env("DB_BOOTSTRAP_RETRIES", 10)
    delay = _float_env("DB_BOOTSTRAP_DELAY_SECONDS", 2.0)
    _bootstrap_shared_with_retry(
        repo_root=repo_root,
        config=config,
        logger=logger,
        retries=retries,
        delay=delay,
    )


def _bootstrap_shared_with_retry(
    *,
    repo_root: Path,
    config: DBConfig,
    logger: logging.Logger,
    retries: int,
    delay: float,
) -> None:
    script_path = repo_root / "backend" / "scripts" / "db_bootstrap.py"
    if not script_path.exists():
        raise RuntimeError(f"db_bootstrap.py not found at {script_path}")
    env = os.environ.copy()
    if config.shared_aggregator_user:
        env["DB_SHARED_AGGREGATOR_USER"] = config.shared_aggregator_user
    if config.shared_aggregator_password:
        env["DB_SHARED_AGGREGATOR_PASSWORD"] = config.shared_aggregator_password
    cmd = [sys.executable, str(script_path), "--shared"]
    if config.shared_aggregator_password:
        cmd += ["--shared-aggregator-password", config.shared_aggregator_password]
    attempt = 0
    while True:
        attempt += 1
        try:
            subprocess.run(cmd, check=True, cwd=str(repo_root), env=env)
            return
        except subprocess.CalledProcessError as exc:
            if attempt >= max(retries, 1):
                raise RuntimeError("Shared DB bootstrap failed") from exc
            logger.warning(
                "Shared DB bootstrap failed (attempt %s/%s); retrying in %.1fs",
                attempt,
                retries,
                delay,
            )
            time.sleep(delay)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
