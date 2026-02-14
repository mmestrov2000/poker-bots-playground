from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuthSettings:
    session_cookie_name: str
    session_cookie_secure: bool | None
    session_ttl_seconds: int
    login_max_failures: int
    login_lockout_seconds: int
    login_failure_window_seconds: int
    bootstrap_username: str
    bootstrap_password: str
    db_path: Path

    @classmethod
    def from_env(cls, repo_root: Path) -> "AuthSettings":
        runtime_dir = _resolve_runtime_dir(repo_root)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        raw_cookie_secure = os.getenv("APP_SESSION_COOKIE_SECURE")
        session_cookie_secure: bool | None
        if raw_cookie_secure is None:
            session_cookie_secure = None
        else:
            session_cookie_secure = raw_cookie_secure.strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            session_cookie_name=os.getenv("APP_SESSION_COOKIE_NAME", "ppg_session"),
            session_cookie_secure=session_cookie_secure,
            session_ttl_seconds=int(os.getenv("APP_SESSION_TTL_SECONDS", "28800")),
            login_max_failures=int(os.getenv("APP_LOGIN_MAX_FAILURES", "5")),
            login_lockout_seconds=int(os.getenv("APP_LOGIN_LOCKOUT_SECONDS", "300")),
            login_failure_window_seconds=int(os.getenv("APP_LOGIN_FAILURE_WINDOW_SECONDS", "300")),
            bootstrap_username=os.getenv("APP_BOOTSTRAP_USERNAME", "demo"),
            bootstrap_password=os.getenv("APP_BOOTSTRAP_PASSWORD", "demo-password"),
            db_path=_resolve_auth_db_path(repo_root=repo_root, runtime_dir=runtime_dir),
        )


def _resolve_runtime_dir(repo_root: Path) -> Path:
    runtime_dir = os.getenv("APP_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir)
    return repo_root / "runtime"


def _resolve_auth_db_path(repo_root: Path, runtime_dir: Path) -> Path:
    explicit_db_path = os.getenv("APP_AUTH_DB_PATH")
    if explicit_db_path:
        return Path(explicit_db_path)

    target_db_path = runtime_dir / "auth.sqlite3"
    if target_db_path.exists():
        return target_db_path

    # Backward compatibility: migrate DB from historical location when present.
    legacy_db_path = repo_root / "backend" / "runtime" / "auth.sqlite3"
    if not legacy_db_path.exists():
        return target_db_path

    try:
        _migrate_auth_db_files(source_db_path=legacy_db_path, target_db_path=target_db_path)
        return target_db_path
    except OSError:
        # Fall back to existing location rather than losing access to existing accounts.
        return legacy_db_path


def _migrate_auth_db_files(source_db_path: Path, target_db_path: Path) -> None:
    target_db_path.parent.mkdir(parents=True, exist_ok=True)
    suffixes = ("", "-wal", "-shm")
    for suffix in suffixes:
        source_path = source_db_path.with_name(f"{source_db_path.name}{suffix}")
        if not source_path.exists():
            continue
        target_path = target_db_path.with_name(f"{target_db_path.name}{suffix}")
        source_path.replace(target_path)
