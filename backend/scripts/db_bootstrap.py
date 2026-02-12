from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from app.db.config import get_db_config  # noqa: E402
from app.db.version import SCHEMA_VERSION  # noqa: E402

SHARED_AGGREGATOR_ROLE = os.getenv("DB_SHARED_AGGREGATOR_USER", "shared_aggregator")
SHARED_AGGREGATOR_PASSWORD = os.getenv("DB_SHARED_AGGREGATOR_PASSWORD")


def _psycopg_dsn(sqlalchemy_dsn: str) -> str:
    return sqlalchemy_dsn.replace("postgresql+psycopg", "postgresql")


def _ensure_role(conn: psycopg.Connection, role: str, password: str) -> None:
    conn.execute(
        sql.SQL(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {role_literal}) THEN
                    CREATE ROLE {role_ident} LOGIN PASSWORD {password_literal};
                ELSE
                    ALTER ROLE {role_ident} LOGIN PASSWORD {password_literal};
                END IF;
            END $$;
            """
        ).format(
            role_literal=sql.Literal(role),
            role_ident=sql.Identifier(role),
            password_literal=sql.Literal(password),
        )
    )


def _ensure_schema(conn: psycopg.Connection, schema: str) -> None:
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))


def _grant_shared_aggregator(conn: psycopg.Connection, shared_schema: str) -> None:
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(shared_schema), sql.Identifier(SHARED_AGGREGATOR_ROLE)
        )
    )
    conn.execute(
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
        ).format(sql.Identifier(shared_schema), sql.Identifier(SHARED_AGGREGATOR_ROLE))
    )
    conn.execute(
        sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(shared_schema), sql.Identifier(SHARED_AGGREGATOR_ROLE)
        )
    )
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(sql.Identifier(shared_schema), sql.Identifier(SHARED_AGGREGATOR_ROLE))
    )
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT USAGE ON SEQUENCES TO {}"
        ).format(sql.Identifier(shared_schema), sql.Identifier(SHARED_AGGREGATOR_ROLE))
    )
    conn.execute(
        sql.SQL("ALTER ROLE {} SET search_path = {}").format(
            sql.Identifier(SHARED_AGGREGATOR_ROLE), sql.Identifier(shared_schema)
        )
    )


def _grant_bot_role(
    conn: psycopg.Connection, bot_role: str, bot_schema: str, shared_schema: str
) -> None:
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(bot_schema), sql.Identifier(bot_role)))
    conn.execute(
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
        ).format(sql.Identifier(bot_schema), sql.Identifier(bot_role))
    )
    conn.execute(
        sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(bot_schema), sql.Identifier(bot_role)
        )
    )
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(sql.Identifier(bot_schema), sql.Identifier(bot_role))
    )
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT USAGE ON SEQUENCES TO {}"
        ).format(sql.Identifier(bot_schema), sql.Identifier(bot_role))
    )
    conn.execute(
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(shared_schema), sql.Identifier(bot_role)
        )
    )
    conn.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
            sql.Identifier(shared_schema), sql.Identifier(bot_role)
        )
    )
    conn.execute(
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}"
        ).format(sql.Identifier(shared_schema), sql.Identifier(bot_role))
    )
    conn.execute(
        sql.SQL("ALTER ROLE {} SET search_path = {}, {}").format(
            sql.Identifier(bot_role),
            sql.Identifier(bot_schema),
            sql.Identifier(shared_schema),
        )
    )


def _run_alembic(schema: str) -> None:
    alembic_ini = BASE_DIR / "alembic.ini"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(alembic_ini),
            "-x",
            f"schema={schema}",
            "upgrade",
            "head",
        ],
        check=True,
        cwd=str(BASE_DIR),
    )


def _verify_schema_version(conn: psycopg.Connection, schema: str) -> None:
    row = conn.execute(
        sql.SQL(
            "SELECT schema_version FROM {}.schema_version WHERE schema_name = %s"
        ).format(sql.Identifier(schema)),
        (schema,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"schema_version missing for {schema}")
    if row[0] != SCHEMA_VERSION:
        raise RuntimeError(f"schema_version mismatch for {schema}: {row[0]}")


def _generate_password() -> str:
    return secrets.token_urlsafe(18)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap bot/shared schemas and roles.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--shared", action="store_true", help="bootstrap shared schema")
    group.add_argument("--bot-id", help="bot id to bootstrap schema and role")
    parser.add_argument("--bot-password", help="password for bot role")
    parser.add_argument(
        "--shared-aggregator-password",
        help="password for shared_aggregator role",
    )
    args = parser.parse_args()

    config = get_db_config()
    shared_schema = config.shared_schema

    admin_dsn = _psycopg_dsn(config.admin_dsn)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        _ensure_schema(conn, shared_schema)

        shared_password = args.shared_aggregator_password or SHARED_AGGREGATOR_PASSWORD or _generate_password()
        _ensure_role(conn, SHARED_AGGREGATOR_ROLE, shared_password)

        if args.shared:
            schema = shared_schema
            _ensure_schema(conn, schema)
            _run_alembic(schema)
            _grant_shared_aggregator(conn, shared_schema)
            _verify_schema_version(conn, schema)
            print(f"shared schema ready: {schema}")
            print(f"{SHARED_AGGREGATOR_ROLE} password: {shared_password}")
            return

        bot_schema = f"{config.private_schema_prefix}{args.bot_id}"
        bot_role = f"{bot_schema}_rw"
        bot_password = args.bot_password or _generate_password()

        _ensure_schema(conn, bot_schema)
        _ensure_role(conn, bot_role, bot_password)
        _run_alembic(bot_schema)
        _grant_bot_role(conn, bot_role, bot_schema, shared_schema)
        _verify_schema_version(conn, bot_schema)
        print(f"bot schema ready: {bot_schema}")
        print(f"bot role: {bot_role}")
        print(f"bot password: {bot_password}")


if __name__ == "__main__":
    main()
