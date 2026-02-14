from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path


class AuthStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    invalidated_at INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY,
                    failure_count INTEGER NOT NULL,
                    first_failed_at INTEGER NOT NULL,
                    last_failed_at INTEGER NOT NULL,
                    locked_until INTEGER
                );
                """
            )

    def create_user(self, username: str, password_hash: str, now_ts: int) -> dict:
        with self._lock, self._connect() as connection:
            user_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO users (user_id, username, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, password_hash, now_ts),
            )
            connection.commit()
            return {
                "user_id": user_id,
                "username": username,
                "password_hash": password_hash,
                "created_at": now_ts,
            }

    def get_user_by_username(self, username: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, username, password_hash, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row is not None else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, username, password_hash, created_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def has_users(self) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
            return row is not None

    def create_session(self, user_id: str, now_ts: int, ttl_seconds: int) -> dict:
        session_id = uuid.uuid4().hex
        expires_at = now_ts + ttl_seconds
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, user_id, created_at, expires_at, invalidated_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (session_id, user_id, now_ts, expires_at),
            )
            connection.commit()
        return {"session_id": session_id, "expires_at": expires_at}

    def get_valid_session(self, session_id: str, now_ts: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_id, user_id, created_at, expires_at, invalidated_at
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            session = dict(row)
            if session["invalidated_at"] is not None:
                return None
            if session["expires_at"] <= now_ts:
                return None
            return session

    def invalidate_session(self, session_id: str, now_ts: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET invalidated_at = ? WHERE session_id = ? AND invalidated_at IS NULL",
                (now_ts, session_id),
            )
            connection.commit()

    def clear_failures(self, username: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
            connection.commit()

    def get_locked_until(self, username: str, now_ts: int) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT locked_until FROM login_attempts WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None:
                return None
            locked_until = row["locked_until"]
            if locked_until is None or locked_until <= now_ts:
                return None
            return int(locked_until)

    def register_login_failure(
        self,
        username: str,
        now_ts: int,
        max_failures: int,
        window_seconds: int,
        lockout_seconds: int,
    ) -> int | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT failure_count, first_failed_at, last_failed_at, locked_until
                FROM login_attempts
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

            if row is None:
                failure_count = 1
                first_failed_at = now_ts
                locked_until = None
            else:
                last_failed_at = int(row["last_failed_at"])
                if now_ts - last_failed_at > window_seconds:
                    failure_count = 1
                    first_failed_at = now_ts
                else:
                    failure_count = int(row["failure_count"]) + 1
                    first_failed_at = int(row["first_failed_at"])
                locked_until = row["locked_until"]

            if failure_count >= max_failures:
                locked_until = now_ts + lockout_seconds

            connection.execute(
                """
                INSERT INTO login_attempts (username, failure_count, first_failed_at, last_failed_at, locked_until)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    failure_count = excluded.failure_count,
                    first_failed_at = excluded.first_failed_at,
                    last_failed_at = excluded.last_failed_at,
                    locked_until = excluded.locked_until
                """,
                (username, failure_count, first_failed_at, now_ts, locked_until),
            )
            connection.commit()
            if locked_until is None or locked_until <= now_ts:
                return None
            return int(locked_until)
