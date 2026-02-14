from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuthSettings:
    session_cookie_name: str
    session_ttl_seconds: int
    login_max_failures: int
    login_lockout_seconds: int
    login_failure_window_seconds: int
    bootstrap_username: str
    bootstrap_password: str
    db_path: Path

    @classmethod
    def from_env(cls, repo_root: Path) -> "AuthSettings":
        runtime_dir = repo_root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            session_cookie_name=os.getenv("APP_SESSION_COOKIE_NAME", "ppg_session"),
            session_ttl_seconds=int(os.getenv("APP_SESSION_TTL_SECONDS", "28800")),
            login_max_failures=int(os.getenv("APP_LOGIN_MAX_FAILURES", "5")),
            login_lockout_seconds=int(os.getenv("APP_LOGIN_LOCKOUT_SECONDS", "300")),
            login_failure_window_seconds=int(os.getenv("APP_LOGIN_FAILURE_WINDOW_SECONDS", "300")),
            bootstrap_username=os.getenv("APP_BOOTSTRAP_USERNAME", "demo"),
            bootstrap_password=os.getenv("APP_BOOTSTRAP_PASSWORD", "demo-password"),
            db_path=Path(os.getenv("APP_AUTH_DB_PATH", str(runtime_dir / "auth.sqlite3"))),
        )
