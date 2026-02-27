import sqlite3
from pathlib import Path

from app.auth.store import AuthStore


def _list_tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def _schema_versions(db_path: Path) -> list[int]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    return [int(row[0]) for row in rows]


def test_auth_store_bootstrap_creates_reproducible_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.sqlite3"

    AuthStore(db_path)

    tables = _list_tables(db_path)
    assert "users" in tables
    assert "sessions" in tables
    assert "login_attempts" in tables
    assert "bot_records" in tables
    assert "table_records" in tables
    assert "leaderboard_rows" in tables
    assert _schema_versions(db_path) == [1, 2]


def test_auth_store_upgrades_legacy_schema_without_losing_auth_data(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                invalidated_at INTEGER
            );
            CREATE TABLE login_attempts (
                username TEXT PRIMARY KEY,
                failure_count INTEGER NOT NULL,
                first_failed_at INTEGER NOT NULL,
                last_failed_at INTEGER NOT NULL,
                locked_until INTEGER
            );
            CREATE TABLE bot_records (
                bot_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            INSERT INTO users (user_id, username, password_hash, created_at)
            VALUES ('legacy-user', 'legacy', 'hash', 1700000000);
            """
        )
        connection.commit()

    store = AuthStore(db_path)

    assert store.get_user_by_username("legacy") is not None
    tables = _list_tables(db_path)
    assert "table_records" in tables
    assert "leaderboard_rows" in tables
    assert _schema_versions(db_path) == [1, 2]


def test_table_and_leaderboard_data_persist_across_store_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "auth.sqlite3"

    first_store = AuthStore(db_path)
    user = first_store.create_user(username="owner", password_hash="hash", now_ts=1700000000)
    bot = first_store.create_bot_record(
        bot_id="bot-1",
        owner_user_id=user["user_id"],
        name="My Bot",
        version="1.0.0",
        artifact_path=str(tmp_path / "bot.zip"),
        now_ts=1700000010,
    )
    first_store.create_table_record(
        table_id="table-1",
        created_by_user_id=user["user_id"],
        small_blind=0.5,
        big_blind=1.0,
        status="waiting",
        now_ts=1700000020,
    )
    first_store.upsert_leaderboard_row(
        bot_id=bot["bot_id"],
        hands_played=40,
        bb_won=10.0,
        updated_at=1700000030,
    )

    restarted_store = AuthStore(db_path)
    table_records = restarted_store.list_table_records()
    leaderboard = restarted_store.list_leaderboard_rows()

    assert len(table_records) == 1
    assert table_records[0]["table_id"] == "table-1"
    assert table_records[0]["created_by_user_id"] == user["user_id"]
    assert len(leaderboard) == 1
    assert leaderboard[0]["bot_id"] == "bot-1"
    assert leaderboard[0]["hands_played"] == 40
    assert leaderboard[0]["bb_won"] == 10.0
    assert leaderboard[0]["bb_per_hand"] == 0.25
