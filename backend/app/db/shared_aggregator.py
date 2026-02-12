from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.db.config import DBConfig, get_db_config


class SharedAggregationWriter:
    def __init__(self, config: DBConfig | None = None) -> None:
        self._config = config or get_db_config()
        self._engine: Engine | None = None
        if self._config.enabled and self._config.shared_aggregator_user and self._config.shared_aggregator_password:
            dsn = self._config.bot_dsn(
                self._config.shared_aggregator_user,
                self._config.shared_aggregator_password,
            )
            separator = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{separator}options=-csearch_path={self._config.shared_schema}"
            self._engine = create_engine(dsn, pool_pre_ping=True)

    @property
    def enabled(self) -> bool:
        return self._engine is not None

    def write_hand(
        self,
        *,
        hand_id: int,
        completed_at: datetime,
        pot: float,
        winners: list[str],
        deltas: dict[str, float],
        leaderboard_entries: Iterable[dict],
    ) -> None:
        if not self._engine:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO shared.hand_aggregates
                        (hand_id, completed_at, pot, winners, deltas)
                    VALUES
                        (:hand_id, :completed_at, :pot, CAST(:winners AS JSONB), CAST(:deltas AS JSONB))
                    ON CONFLICT (hand_id)
                    DO UPDATE SET completed_at = EXCLUDED.completed_at,
                                  pot = EXCLUDED.pot,
                                  winners = EXCLUDED.winners,
                                  deltas = EXCLUDED.deltas
                    """
                ),
                {
                    "hand_id": hand_id,
                    "completed_at": completed_at,
                    "pot": pot,
                    "winners": json.dumps(winners),
                    "deltas": json.dumps(deltas),
                },
            )
            for entry in leaderboard_entries:
                conn.execute(
                    text(
                        """
                        INSERT INTO shared.bot_leaderboard
                            (bot_id, hands_played, bb_per_hand, updated_at)
                        VALUES
                            (:bot_id, :hands_played, :bb_per_hand, :updated_at)
                        ON CONFLICT (bot_id)
                        DO UPDATE SET hands_played = EXCLUDED.hands_played,
                                      bb_per_hand = EXCLUDED.bb_per_hand,
                                      updated_at = EXCLUDED.updated_at
                        """
                    ),
                    entry,
                )
