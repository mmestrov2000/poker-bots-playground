from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path


class AuthStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        self._harden_permissions()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            PRAGMA foreign_keys=ON;
            PRAGMA secure_delete=ON;
            """
        )

    def _harden_permissions(self) -> None:
        """
        Best-effort filesystem hardening for auth data at rest.
        """
        targets = [
            self._db_path,
            self._db_path.with_name(f"{self._db_path.name}-wal"),
            self._db_path.with_name(f"{self._db_path.name}-shm"),
        ]
        for target in targets:
            if not target.exists():
                continue
            try:
                target.chmod(0o600)
            except OSError:
                # Ignore permission-setting failures on constrained filesystems.
                continue

    def _init_db(self) -> None:
        with self._connect() as connection:
            self._configure_connection(connection)
            existing_tables = self._list_tables(connection)
            self._ensure_migrations_table(connection)
            if self._is_legacy_schema(existing_tables):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO schema_migrations (version, applied_at)
                    VALUES (?, ?)
                    """,
                    (1, int(time.time())),
                )

            current_version = self._current_schema_version(connection)
            for version, migration_sql in self._ordered_migrations():
                if version <= current_version:
                    continue
                connection.executescript(migration_sql)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, applied_at)
                    VALUES (?, ?)
                    """,
                    (version, int(time.time())),
                )
            connection.commit()

    def _list_tables(self, connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_migrations_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
            """
        )

    def _is_legacy_schema(self, tables: set[str]) -> bool:
        legacy_tables = {"users", "sessions", "login_attempts", "bot_records"}
        return legacy_tables.issubset(tables) and "schema_migrations" not in tables

    def _current_schema_version(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT MAX(version) AS version FROM schema_migrations"
        ).fetchone()
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])

    def _ordered_migrations(self) -> list[tuple[int, str]]:
        return [
            (
                1,
                """
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
                CREATE TABLE IF NOT EXISTS bot_records (
                    bot_id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY(owner_user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_bot_records_owner_user_id
                    ON bot_records(owner_user_id, created_at DESC);
                """,
            ),
            (
                2,
                """
                CREATE TABLE IF NOT EXISTS table_records (
                    table_id TEXT PRIMARY KEY,
                    created_by_user_id TEXT NOT NULL,
                    small_blind REAL NOT NULL,
                    big_blind REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY(created_by_user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_table_records_created_at
                    ON table_records(created_at DESC, table_id DESC);
                CREATE TABLE IF NOT EXISTS leaderboard_rows (
                    bot_id TEXT PRIMARY KEY,
                    hands_played INTEGER NOT NULL,
                    bb_won REAL NOT NULL,
                    updated_at INTEGER NOT NULL,
                    FOREIGN KEY(bot_id) REFERENCES bot_records(bot_id)
                );
                CREATE INDEX IF NOT EXISTS idx_leaderboard_rows_rank
                    ON leaderboard_rows(hands_played DESC, bb_won DESC, bot_id DESC);
                """,
            ),
        ]

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

    def create_bot_record(
        self,
        *,
        bot_id: str,
        owner_user_id: str,
        name: str,
        version: str,
        artifact_path: str,
        now_ts: int,
    ) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO bot_records (bot_id, owner_user_id, name, version, artifact_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bot_id, owner_user_id, name, version, artifact_path, now_ts),
            )
            connection.commit()
        return {
            "bot_id": bot_id,
            "owner_user_id": owner_user_id,
            "name": name,
            "version": version,
            "artifact_path": artifact_path,
            "created_at": now_ts,
        }

    def list_bot_records_by_owner(self, owner_user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT bot_id, owner_user_id, name, version, artifact_path, created_at
                FROM bot_records
                WHERE owner_user_id = ?
                ORDER BY created_at DESC, bot_id DESC
                """,
                (owner_user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_bot_record(self, bot_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT bot_id, owner_user_id, name, version, artifact_path, created_at
                FROM bot_records
                WHERE bot_id = ?
                """,
                (bot_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def create_table_record(
        self,
        *,
        table_id: str,
        created_by_user_id: str,
        small_blind: float,
        big_blind: float,
        status: str,
        now_ts: int,
    ) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO table_records (
                    table_id,
                    created_by_user_id,
                    small_blind,
                    big_blind,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (table_id, created_by_user_id, small_blind, big_blind, status, now_ts),
            )
            connection.commit()
        return {
            "table_id": table_id,
            "created_by_user_id": created_by_user_id,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "status": status,
            "created_at": now_ts,
        }

    def list_table_records(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT table_id, created_by_user_id, small_blind, big_blind, status, created_at
                FROM table_records
                ORDER BY created_at DESC, table_id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_leaderboard_row(
        self,
        *,
        bot_id: str,
        hands_played: int,
        bb_won: float,
        updated_at: int,
    ) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO leaderboard_rows (bot_id, hands_played, bb_won, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(bot_id) DO UPDATE SET
                    hands_played = excluded.hands_played,
                    bb_won = excluded.bb_won,
                    updated_at = excluded.updated_at
                """,
                (bot_id, hands_played, bb_won, updated_at),
            )
            connection.commit()
        return {
            "bot_id": bot_id,
            "hands_played": hands_played,
            "bb_won": bb_won,
            "updated_at": updated_at,
        }

    def get_leaderboard_row(self, bot_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    bot_id,
                    hands_played,
                    bb_won,
                    CASE
                        WHEN hands_played > 0 THEN bb_won * 1.0 / hands_played
                        ELSE 0.0
                    END AS bb_per_hand,
                    updated_at
                FROM leaderboard_rows
                WHERE bot_id = ?
                """,
                (bot_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_leaderboard_rows(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    bot_id,
                    hands_played,
                    bb_won,
                    CASE
                        WHEN hands_played > 0 THEN bb_won * 1.0 / hands_played
                        ELSE 0.0
                    END AS bb_per_hand,
                    updated_at
                FROM leaderboard_rows
                ORDER BY bb_per_hand DESC, hands_played DESC, updated_at DESC, bot_id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
