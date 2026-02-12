"""baseline schemas

Revision ID: 0001_baseline
Revises: 
Create Date: 2025-09-11 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.config import get_db_config
from app.db.version import SCHEMA_VERSION

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _schema() -> str:
    args = op.get_context().get_x_argument(as_dictionary=True)
    schema = args.get("schema")
    if not schema:
        raise ValueError("schema is required; pass -x schema=<name>")
    return schema


def _is_shared(schema: str) -> bool:
    return schema == get_db_config().shared_schema


def _create_schema(schema: str) -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def _create_schema_version(schema: str) -> None:
    op.create_table(
        "schema_version",
        sa.Column("schema_name", sa.Text(), primary_key=True),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("alembic_revision", sa.Text(), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )


def _upsert_schema_version(schema: str) -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO "{schema}".schema_version
                (schema_name, schema_version, alembic_revision, applied_at)
            VALUES (:schema_name, :schema_version, :alembic_revision, now())
            ON CONFLICT (schema_name)
            DO UPDATE SET schema_version = EXCLUDED.schema_version,
                          alembic_revision = EXCLUDED.alembic_revision,
                          applied_at = EXCLUDED.applied_at
            """
        ).bindparams(
            schema_name=schema,
            schema_version=SCHEMA_VERSION,
            alembic_revision=revision,
        )
    )


def _create_shared_tables(schema: str) -> None:
    op.create_table(
        "opponent_profiles",
        sa.Column("bot_id", sa.Text(), primary_key=True),
        sa.Column("stats_json", postgresql.JSONB(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_table(
        "hand_aggregates",
        sa.Column("hand_id", sa.Integer(), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pot", sa.Numeric(), nullable=True),
        sa.Column("winners", postgresql.JSONB(), nullable=True),
        sa.Column("deltas", postgresql.JSONB(), nullable=True),
        schema=schema,
    )
    op.create_table(
        "bot_leaderboard",
        sa.Column("bot_id", sa.Text(), primary_key=True),
        sa.Column("hands_played", sa.Integer(), nullable=True),
        sa.Column("bb_per_hand", sa.Numeric(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )


def _create_bot_tables(schema: str) -> None:
    op.create_table(
        "bot_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state_json", postgresql.JSONB(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_table(
        "model_params",
        sa.Column("param_key", sa.Text(), primary_key=True),
        sa.Column("param_value", postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_table(
        "decision_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("hand_id", sa.Integer(), nullable=True),
        sa.Column("seat_id", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("state_hash", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema,
    )
    op.create_index("ix_decision_log_hand_id", "decision_log", ["hand_id"], schema=schema)
    op.create_index("ix_decision_log_created_at", "decision_log", ["created_at"], schema=schema)


def upgrade() -> None:
    schema = _schema()
    _create_schema(schema)
    _create_schema_version(schema)
    if _is_shared(schema):
        _create_shared_tables(schema)
    else:
        _create_bot_tables(schema)
    _upsert_schema_version(schema)


def downgrade() -> None:
    schema = _schema()
    if _is_shared(schema):
        op.drop_table("bot_leaderboard", schema=schema)
        op.drop_table("hand_aggregates", schema=schema)
        op.drop_table("opponent_profiles", schema=schema)
    else:
        op.drop_index("ix_decision_log_created_at", table_name="decision_log", schema=schema)
        op.drop_index("ix_decision_log_hand_id", table_name="decision_log", schema=schema)
        op.drop_table("decision_log", schema=schema)
        op.drop_table("model_params", schema=schema)
        op.drop_table("bot_state", schema=schema)
    op.drop_table("schema_version", schema=schema)
